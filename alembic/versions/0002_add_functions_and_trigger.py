"""add plpgsql functions and trigger

Revision ID: 0002
Revises: 0001
Create Date: 2025-08-24 00:00:00

"""
from __future__ import annotations

from alembic import op


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        r'''
        CREATE OR REPLACE FUNCTION update_lesson_progress_on_attempt(p_attempt_id bigint)
        RETURNS void LANGUAGE plpgsql AS $$
        DECLARE
            v_user_id bigint;
            v_task_id bigint;
            v_lesson_id bigint;
            v_is_correct boolean;
        BEGIN
            SELECT ta.user_id, ta.task_id, t.lesson_id, ta.is_correct
            INTO v_user_id, v_task_id, v_lesson_id, v_is_correct
            FROM task_attempt ta
            JOIN task t ON t.id = ta.task_id
            WHERE ta.id = p_attempt_id;

            INSERT INTO lesson_progress (user_id, lesson_id, attempts, correct, accuracy, mastered, last_attempt_at)
            VALUES (v_user_id, v_lesson_id, 1, CASE WHEN v_is_correct THEN 1 ELSE 0 END, CASE WHEN v_is_correct THEN 1 ELSE 0 END, FALSE, now())
            ON CONFLICT (user_id, lesson_id)
            DO UPDATE SET
                attempts = lesson_progress.attempts + 1,
                correct = lesson_progress.correct + CASE WHEN v_is_correct THEN 1 ELSE 0 END,
                accuracy = (lesson_progress.correct + CASE WHEN v_is_correct THEN 1 ELSE 0 END)::float / (lesson_progress.attempts + 1),
                last_attempt_at = now();
        END;
        $$;
        '''
    )

    op.execute(
        r'''
        CREATE OR REPLACE FUNCTION update_topic_stats_on_attempt(p_attempt_id bigint)
        RETURNS void LANGUAGE plpgsql AS $$
        DECLARE
            v_user_id bigint;
            v_topic text;
            v_is_correct boolean;
        BEGIN
            SELECT ta.user_id, COALESCE(t.topic, 'unknown'), ta.is_correct
            INTO v_user_id, v_topic, v_is_correct
            FROM task_attempt ta
            JOIN task t ON t.id = ta.task_id
            WHERE ta.id = p_attempt_id;

            INSERT INTO topic_stats (user_id, topic, attempts, correct, accuracy)
            VALUES (v_user_id, v_topic, 1, CASE WHEN v_is_correct THEN 1 ELSE 0 END, CASE WHEN v_is_correct THEN 1 ELSE 0 END)
            ON CONFLICT (user_id, topic)
            DO UPDATE SET
                attempts = topic_stats.attempts + 1,
                correct = topic_stats.correct + CASE WHEN v_is_correct THEN 1 ELSE 0 END,
                accuracy = (topic_stats.correct + CASE WHEN v_is_correct THEN 1 ELSE 0 END)::float / (topic_stats.attempts + 1);
        END;
        $$;
        '''
    )

    op.execute(
        r'''
        CREATE OR REPLACE FUNCTION recompute_mastered_on_attempt(p_attempt_id bigint)
        RETURNS void LANGUAGE plpgsql AS $$
        DECLARE
            v_user_id bigint;
            v_lesson_id bigint;
            v_task_id bigint;
            v_attempts int;
            v_correct int;
            v_last_three_correct int;
            v_accuracy float;
        BEGIN
            SELECT ta.user_id, t.lesson_id, ta.task_id
            INTO v_user_id, v_lesson_id, v_task_id
            FROM task_attempt ta
            JOIN task t ON t.id = ta.task_id
            WHERE ta.id = p_attempt_id;

            SELECT attempts, correct, accuracy
            INTO v_attempts, v_correct, v_accuracy
            FROM lesson_progress
            WHERE user_id = v_user_id AND lesson_id = v_lesson_id;

            SELECT COUNT(*)
            INTO v_last_three_correct
            FROM (
                SELECT is_correct
                FROM task_attempt
                WHERE user_id = v_user_id AND task_id = v_task_id
                ORDER BY submitted_at DESC
                LIMIT 3
            ) s
            WHERE s.is_correct = TRUE;

            IF v_last_three_correct = 3 OR (v_attempts >= 10 AND v_accuracy >= 0.9) THEN
                UPDATE lesson_progress
                SET mastered = TRUE
                WHERE user_id = v_user_id AND lesson_id = v_lesson_id;
            END IF;
        END;
        $$;
        '''
    )

    op.execute(
        r'''
        CREATE OR REPLACE FUNCTION task_attempt_after_insert_fn()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            PERFORM update_lesson_progress_on_attempt(NEW.id);
            PERFORM update_topic_stats_on_attempt(NEW.id);
            PERFORM recompute_mastered_on_attempt(NEW.id);
            RETURN NEW;
        END;
        $$;

        DROP TRIGGER IF EXISTS trg_task_attempt_after_insert ON task_attempt;
        CREATE TRIGGER trg_task_attempt_after_insert
        AFTER INSERT ON task_attempt
        FOR EACH ROW
        EXECUTE FUNCTION task_attempt_after_insert_fn();
        '''
    )


def downgrade() -> None:
    op.execute('DROP TRIGGER IF EXISTS trg_task_attempt_after_insert ON task_attempt;')
    op.execute('DROP FUNCTION IF EXISTS task_attempt_after_insert_fn();')
    op.execute('DROP FUNCTION IF EXISTS recompute_mastered_on_attempt(bigint);')
    op.execute('DROP FUNCTION IF EXISTS update_topic_stats_on_attempt(bigint);')
    op.execute('DROP FUNCTION IF EXISTS update_lesson_progress_on_attempt(bigint);')

