from alembic import op


revision = "0004_agg_funcs_support_no_lesson_id"
down_revision = "0003_fix_subtopic_code_type"  # or "0002_agg_funcs" if 0003 is not present
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    -- Update functions to take lesson_id from task_attempt.lesson_id OR from task.lesson_id
    CREATE OR REPLACE FUNCTION update_lesson_progress_on_attempt(p_attempt_id BIGINT)
    RETURNS VOID AS $$
    DECLARE
      v_user_id BIGINT;
      v_lesson_id BIGINT;
      v_is_correct BOOLEAN;
      v_finished_at TIMESTAMPTZ;
    BEGIN
      SELECT ta.user_id,
             COALESCE(ta.lesson_id, t.lesson_id) AS lesson_id,
             ta.is_correct,
             COALESCE(ta.finished_at, now()) AS finished_at
      INTO v_user_id, v_lesson_id, v_is_correct, v_finished_at
      FROM task_attempt ta
      LEFT JOIN task t ON t.id = ta.task_id
      WHERE ta.id = p_attempt_id;

      IF v_lesson_id IS NULL THEN
        RAISE EXCEPTION 'Cannot determine lesson_id for attempt %', p_attempt_id;
      END IF;

      -- In current schema lesson_progress has attempts / correct / last_seen_at
      INSERT INTO lesson_progress AS lp (user_id, lesson_id, attempts, correct, last_seen_at, mastered)
      VALUES (v_user_id, v_lesson_id, 1, CASE WHEN v_is_correct THEN 1 ELSE 0 END, v_finished_at, FALSE)
      ON CONFLICT (user_id, lesson_id) DO UPDATE
      SET attempts = lp.attempts + 1,
          correct  = lp.correct  + CASE WHEN v_is_correct THEN 1 ELSE 0 END,
          last_seen_at = GREATEST(lp.last_seen_at, EXCLUDED.last_seen_at);
    END;
    $$ LANGUAGE plpgsql;

    CREATE OR REPLACE FUNCTION update_topic_stats_on_attempt(p_attempt_id BIGINT)
    RETURNS VOID AS $$
    DECLARE
      v_user_id BIGINT;
      v_lesson_id BIGINT;
      v_is_correct BOOLEAN;
      v_finished_at TIMESTAMPTZ;
      v_topic TEXT;
      v_subtopic TEXT;
    BEGIN
      SELECT ta.user_id,
             COALESCE(ta.lesson_id, t.lesson_id) AS lesson_id,
             ta.is_correct,
             COALESCE(ta.finished_at, now()) AS finished_at
      INTO v_user_id, v_lesson_id, v_is_correct, v_finished_at
      FROM task_attempt ta
      LEFT JOIN task t ON t.id = ta.task_id
      WHERE ta.id = p_attempt_id;

      SELECT l.topic_code, l.subtopic_code
      INTO v_topic, v_subtopic
      FROM lesson l
      WHERE l.id = v_lesson_id;

      INSERT INTO topic_stats AS ts (user_id, topic_code, subtopic_code, attempts, correct, last_seen_at)
      VALUES (v_user_id, v_topic, v_subtopic, 1, CASE WHEN v_is_correct THEN 1 ELSE 0 END, v_finished_at)
      ON CONFLICT (user_id, topic_code, subtopic_code) DO UPDATE
      SET attempts = ts.attempts + 1,
          correct  = ts.correct  + CASE WHEN v_is_correct THEN 1 ELSE 0 END,
          last_seen_at = GREATEST(ts.last_seen_at, EXCLUDED.last_seen_at);
    END;
    $$ LANGUAGE plpgsql;

    CREATE OR REPLACE FUNCTION recompute_mastered_on_attempt(p_attempt_id BIGINT)
    RETURNS VOID AS $$
    DECLARE
      v_user_id BIGINT;
      v_lesson_id BIGINT;
      v_attempts INT;
      v_correct INT;
      v_recent3_correct INT;
      v_accuracy NUMERIC;
    BEGIN
      SELECT ta.user_id,
             COALESCE(ta.lesson_id, t.lesson_id) AS lesson_id
      INTO v_user_id, v_lesson_id
      FROM task_attempt ta
      LEFT JOIN task t ON t.id = ta.task_id
      WHERE ta.id = p_attempt_id;

      -- aggregates at the time of attempt
      SELECT attempts, correct
      INTO v_attempts, v_correct
      FROM lesson_progress
      WHERE user_id = v_user_id AND lesson_id = v_lesson_id;

      IF v_attempts IS NULL THEN
        RETURN;
      END IF;

      v_accuracy := CASE WHEN v_attempts > 0 THEN v_correct::NUMERIC / v_attempts ELSE 0 END;

      -- 3 most recent attempts for the lesson
      SELECT COUNT(*) INTO v_recent3_correct
      FROM (
        SELECT ta.is_correct
        FROM task_attempt ta
        LEFT JOIN task t ON t.id = ta.task_id
        WHERE ta.user_id = v_user_id AND COALESCE(ta.lesson_id, t.lesson_id) = v_lesson_id
        ORDER BY COALESCE(ta.finished_at, ta.submitted_at) DESC
        LIMIT 3
      ) t3
      WHERE t3.is_correct = TRUE;

      UPDATE lesson_progress
      SET mastered = (
        (v_recent3_correct = 3) OR
        (v_attempts >= 10 AND v_accuracy >= 0.9)
      )
      WHERE user_id = v_user_id AND lesson_id = v_lesson_id;
    END;
    $$ LANGUAGE plpgsql;

    -- Recreate trigger to ensure it points to the latest aggregator function
    DROP TRIGGER IF EXISTS trg_task_attempt_after_insert ON task_attempt;
    DROP TRIGGER IF EXISTS trg_task_attempt_aggregate ON task_attempt;
    CREATE TRIGGER trg_task_attempt_aggregate
    AFTER INSERT ON task_attempt
    FOR EACH ROW
    EXECUTE FUNCTION apply_all_aggregations_on_attempt();
    """
    )


def downgrade():
    # Keep functions as they are; no-op downgrade for compatibility
    pass

