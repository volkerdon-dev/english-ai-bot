"""init schema

Revision ID: 0001
Revises: 
Create Date: 2025-08-24 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # app_user
    op.create_table(
        'app_user',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('email', sa.String(length=255), nullable=False, unique=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # lesson
    op.create_table(
        'lesson',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('topic', sa.String(length=128), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # task
    op.create_table(
        'task',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('lesson_id', sa.BigInteger(), sa.ForeignKey('lesson.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('answer', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('topic', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # task indexes
    op.create_index('idx_task_lesson', 'task', ['lesson_id'])

    # task_attempt
    op.create_table(
        'task_attempt',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('app_user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('task_id', sa.BigInteger(), sa.ForeignKey('task.id', ondelete='CASCADE'), nullable=False),
        sa.Column('submitted_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('response', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # indexes on task_attempt
    op.execute('CREATE INDEX IF NOT EXISTS idx_attempt_user_time ON task_attempt (user_id, finished_at DESC);')
    op.execute('CREATE INDEX IF NOT EXISTS idx_attempt_error_tags_gin ON task_attempt USING GIN (error_tags);')

    # lesson_progress
    op.create_table(
        'lesson_progress',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('app_user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lesson_id', sa.BigInteger(), sa.ForeignKey('lesson.id', ondelete='CASCADE'), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('correct', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('accuracy', sa.Float(), nullable=False, server_default='0'),
        sa.Column('mastered', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('last_attempt_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint('user_id', 'lesson_id', name='uq_lesson_progress_user_lesson'),
    )

    op.create_index('idx_progress_mastered', 'lesson_progress', ['user_id', 'mastered'])

    # topic_stats
    op.create_table(
        'topic_stats',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('app_user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('topic', sa.String(length=128), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('correct', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('accuracy', sa.Float(), nullable=False, server_default='0'),
        sa.UniqueConstraint('user_id', 'topic', name='uq_topic_stats_user_topic'),
    )

    # study_session
    op.create_table(
        'study_session',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('app_user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('ended_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('stats', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('study_session')
    op.drop_table('topic_stats')
    op.drop_index('idx_progress_mastered', table_name='lesson_progress')
    op.drop_table('lesson_progress')
    op.execute('DROP INDEX IF EXISTS idx_attempt_error_tags_gin;')
    op.execute('DROP INDEX IF EXISTS idx_attempt_user_time;')
    op.drop_table('task_attempt')
    op.drop_index('idx_task_lesson', table_name='task')
    op.drop_table('task')
    op.drop_table('lesson')
    op.drop_table('app_user')

