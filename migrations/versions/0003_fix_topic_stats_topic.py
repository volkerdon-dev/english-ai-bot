"""fix topic_stats to use lesson.topic

Revision ID: 0003
Revises: 0002
Create Date: 2025-08-28 00:00:00

"""
from __future__ import annotations

from alembic import op


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        r'''
        CREATE OR REPLACE FUNCTION update_topic_stats_on_attempt(p_attempt_id bigint)
        RETURNS void LANGUAGE plpgsql AS $$
        DECLARE
            v_user_id bigint;
            v_topic text;
            v_is_correct boolean;
        BEGIN
            SELECT ta.user_id, COALESCE(l.topic, 'unknown'), ta.is_correct
            INTO v_user_id, v_topic, v_is_correct
            FROM task_attempt ta
            JOIN task t ON t.id = ta.task_id
            JOIN lesson l ON l.id = t.lesson_id
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


def downgrade() -> None:
    # no-op downgrade; keep fixed behavior
    pass

