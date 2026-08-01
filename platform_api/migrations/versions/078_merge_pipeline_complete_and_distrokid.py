"""Merge migration: reconcile pipeline-complete and DistroKid lineages.

Sandbox's `alembic_version` table was found holding two independent, un-merged
heads simultaneously (`075_batch_channel_pipeline_complete` and
`077_batch_auto_distrokid`) — both branches were fully upgraded on that DB at
some point without ever being reconciled with a merge revision. That leaves
`alembic upgrade head` broken for *any* future deploy (Alembic refuses a bare
"head" target when 2+ heads exist), independent of any other feature work.

This is a pure bookkeeping merge: it does not alter schema and does not wire
up DistroKid's router/services (those remain unregistered in `main.py` on
purpose — DistroKid is parked, unreleased future work, see
`feature/distrokid`). It only gives the migration graph a single head again so
`076_distrokid_wav`-descended history and
`075_batch_channel_pipeline_complete`-descended history (this branch's own
work) can coexist and future migrations have one unambiguous parent.

Revision ID: 078_merge_pipeline_complete_and_distrokid
Revises: 077_batch_auto_distrokid, 075_batch_channel_pipeline_complete
Create Date: 2026-08-01
"""

from __future__ import annotations


revision = "078_merge_pipeline_complete_and_distrokid"
down_revision = ("077_batch_auto_distrokid", "075_batch_channel_pipeline_complete")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
