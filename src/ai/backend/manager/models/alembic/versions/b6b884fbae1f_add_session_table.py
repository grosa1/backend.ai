"""add_session_table

Revision ID: b6b884fbae1f
Revises: cace152eefac
Create Date: 2022-12-05 16:12:53.275671

"""
from collections import defaultdict
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from more_itertools import chunked
from sqlalchemy.dialects import postgresql as pgsql
from sqlalchemy.orm import registry

from ai.backend.manager.models import KernelStatus, SessionStatus
from ai.backend.manager.models.base import GUID, KernelIDColumn, convention
from ai.backend.manager.models.session import SessionDependencyRow

# revision identifiers, used by Alembic.
revision = "b6b884fbae1f"
down_revision = "cace152eefac"
branch_labels = None
depends_on = None


kernel_status = tuple(s.name for s in KernelStatus)

session_status = tuple(s.name for s in SessionStatus)

metadata = sa.MetaData(naming_convention=convention)
mapper_registry = registry(metadata=metadata)
Base = mapper_registry.generate_base()

QUERY_CHUNK_SIZE = 100


def default_hostname(context) -> str:
    params = context.get_current_parameters()
    return f"{params['cluster_role']}{params['cluster_idx']}"


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    connection = op.get_bind()
    kernels = sa.Table(
        "kernels",
        metadata,
        KernelIDColumn(),
        sa.Column("session_id", GUID, nullable=False),
        sa.Column("session_creation_id", sa.String(length=32), unique=False),
        sa.Column("session_name", sa.String(length=64), unique=False),
        sa.Column(
            "session_type",
            pgsql.ENUM("INTERACTIVE", "BATCH"),
            nullable=False,
            default="INTERACTIVE",
            server_default="INTERACTIVE",
        ),
        sa.Column("cluster_role", sa.String(length=16), nullable=False, default="main"),
        sa.Column(
            "cluster_mode",
            sa.String(length=16),
            nullable=False,
            default="SINGLE_NODE",
            server_default="SINGLE_NODE",
        ),
        sa.Column("cluster_size", sa.Integer, nullable=False, default=1),
        # Resource ownership
        sa.Column("scaling_group", sa.ForeignKey("scaling_groups.name"), nullable=True),
        sa.Column(
            "domain_name", sa.String(length=64), sa.ForeignKey("domains.name"), nullable=False
        ),
        sa.Column("group_id", GUID, sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("user_uuid", GUID, sa.ForeignKey("users.uuid"), nullable=False),
        sa.Column("access_key", sa.String(length=20), sa.ForeignKey("keypairs.access_key")),
        sa.Column("image", sa.String(length=512)),
        sa.Column("tag", sa.String(length=64), nullable=True),
        # Resource occupation
        sa.Column("occupied_slots", pgsql.JSONB(), nullable=False),
        sa.Column("vfolder_mounts", pgsql.JSONB(), nullable=True),
        sa.Column("resource_opts", pgsql.JSONB(), nullable=True, default={}),
        sa.Column("bootstrap_script", sa.String(length=16 * 1024), nullable=True),
        sa.Column("use_host_network", sa.Boolean(), default=False, nullable=False),
        # Lifecycle
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True, default=sa.null()),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True, default=sa.null()),
        sa.Column(
            "status",
            sa.Enum(*kernel_status),
            default="PENDING",
            server_default="PENDING",
            nullable=False,
        ),
        # sa.Column("status_changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_history", pgsql.JSONB(), nullable=True, default=sa.null()),
        sa.Column("status_info", sa.Unicode(), nullable=True, default=sa.null()),
        sa.Column("status_data", pgsql.JSONB(), nullable=True, default=sa.null()),
        sa.Column("callback_url", sa.types.UnicodeText, nullable=True, default=sa.null()),
        sa.Column("startup_command", sa.Text, nullable=True),
        sa.Column(
            "result",
            sa.Enum("UNDEFINED", "SUCCESS", "FAILURE"),
            default="UNDEFINED",
            server_default="UNDEFINED",
            nullable=False,
        ),
        # Resource metrics measured upon termination
        sa.Column("num_queries", sa.BigInteger(), default=0),
        sa.Column("last_stat", pgsql.JSONB(), nullable=True, default=sa.null()),
    )

    class SessionRow(Base):
        __tablename__ = "sessions"
        id = sa.Column(
            "id",
            GUID(),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
            primary_key=True,
        )
        creation_id = sa.Column("creation_id", sa.String(length=32), unique=False)
        name = sa.Column("name", sa.String(length=64), unique=False)
        session_type = sa.Column(
            "session_type",
            pgsql.ENUM("INTERACTIVE", "BATCH", name="sessiontypes", create_type=False),
            server_default="INTERACTIVE",
            nullable=False,
        )
        cluster_mode = sa.Column(
            "cluster_mode", sa.String(length=16), server_default="SINGLE_NODE", nullable=False
        )
        cluster_size = sa.Column("cluster_size", sa.Integer(), nullable=False)

        # Resource ownership
        scaling_group_name = sa.Column("scaling_group_name", sa.String(length=64), nullable=True)
        target_sgroup_names = sa.Column(
            "target_sgroup_names",
            sa.ARRAY(sa.String(length=64)),
            server_default="{}",
            nullable=True,
        )
        domain_name = sa.Column("domain_name", sa.String(length=64), nullable=False)
        group_id = sa.Column("group_id", GUID(), nullable=False)
        user_uuid = sa.Column("user_uuid", GUID(), nullable=False)
        access_key = sa.Column("access_key", sa.String(length=20), nullable=True)
        # kp_resource_policy = sa.Column(
        #     'kp_resource_policy', sa.String(length=256), nullable=False)

        # # if image_id is null, should find a image field from related kernel row.
        # image_id = sa.Column("image_id", GUID(), nullable=True)
        # # `image` column is identical to kernels `image` column.
        # image = sa.Column("image", sa.String(length=512))
        tag = sa.Column("tag", sa.String(length=64), nullable=True)

        # Resource occupation
        occupying_slots = sa.Column("occupying_slots", pgsql.JSONB(), nullable=False)
        requested_slots = sa.Column("requested_slots", pgsql.JSONB(), nullable=False)
        vfolder_mounts = sa.Column("vfolder_mounts", pgsql.JSONB(), nullable=True)
        resource_opts = sa.Column("resource_opts", pgsql.JSONB(), nullable=True, default={})
        environ = sa.Column("environ", pgsql.JSONB(), nullable=True)
        bootstrap_script = sa.Column("bootstrap_script", sa.String(length=16 * 1024), nullable=True)
        use_host_network = sa.Column(
            "use_host_network", sa.Boolean(), default=False, nullable=False
        )

        # Lifecycle
        timeout = sa.Column("timeout", sa.BigInteger(), nullable=True)
        created_at = sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        )
        terminated_at = sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True)
        starts_at = sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True)
        status = sa.Column(
            "status",
            pgsql.ENUM(
                *session_status,
                name="sessionstatus",
                create_type=True,
            ),
            server_default="PENDING",
            nullable=False,
        )
        # status_changed = sa.Column("status_changed", sa.DateTime(timezone=True), nullable=True)
        status_history = sa.Column(
            "status_history", pgsql.JSONB(), nullable=True, default=sa.null()
        )
        status_info = sa.Column("status_info", sa.Unicode(), nullable=True)
        status_data = sa.Column("status_data", pgsql.JSONB(astext_type=sa.Text()), nullable=True)
        callback_url = sa.Column("callback_url", sa.types.UnicodeText(), nullable=True)

        startup_command = sa.Column("startup_command", sa.Text(), nullable=True)
        result = sa.Column(
            "result",
            pgsql.ENUM("UNDEFINED", "SUCCESS", "FAILURE", name="sessionresults", create_type=True),
            server_default="UNDEFINED",
            nullable=False,
        )

        # Resource metrics measured upon termination
        num_queries = sa.Column("num_queries", sa.BigInteger(), nullable=True)
        last_stat = sa.Column("last_stat", pgsql.JSONB(astext_type=sa.Text()), nullable=True)

    SessionRow.__table__.create(connection)
    op.create_foreign_key(
        op.f("fk_sessions_access_key_keypairs"),
        "sessions",
        "keypairs",
        ["access_key"],
        ["access_key"],
    )
    op.create_foreign_key(
        op.f("fk_sessions_domain_name_domains"), "sessions", "domains", ["domain_name"], ["name"]
    )
    op.create_foreign_key(
        op.f("fk_sessions_group_id_groups"), "sessions", "groups", ["group_id"], ["id"]
    )
    # op.create_foreign_key(
    #     op.f("fk_sessions_image_images"), "sessions", "images", ["image_id"], ["id"]
    # )
    op.create_foreign_key(
        op.f("fk_sessions_scaling_group_scaling_groups"),
        "sessions",
        "scaling_groups",
        ["scaling_group_name"],
        ["name"],
    )
    op.create_foreign_key(
        op.f("fk_sessions_user_uuid_users"), "sessions", "users", ["user_uuid"], ["uuid"]
    )
    op.create_index(op.f("ix_sessions_created_at"), "sessions", ["created_at"], unique=False)
    op.create_index(op.f("ix_sessions_name"), "sessions", ["name"], unique=False)
    op.create_index(op.f("ix_sessions_result"), "sessions", ["result"], unique=False)
    op.create_index(
        op.f("ix_sessions_scaling_group_name"), "sessions", ["scaling_group_name"], unique=False
    )
    op.create_index(op.f("ix_sessions_session_type"), "sessions", ["session_type"], unique=False)
    # op.create_index(op.f("ix_sessions_status"), "sessions", ["status"], unique=False)
    # op.create_index(
    #     op.f("ix_sessions_status_changed"), "sessions", ["status_changed"], unique=False
    # )
    op.create_index(op.f("ix_sessions_terminated_at"), "sessions", ["terminated_at"], unique=False)

    op.drop_constraint(
        "fk_session_dependencies_depends_on_kernels", "session_dependencies", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_session_dependencies_session_id_kernels", "session_dependencies", type_="foreignkey"
    )

    kernel_cnt = connection.execute(sa.select([sa.func.count()]).select_from(kernels)).scalar()
    for chunk in range(0, kernel_cnt, QUERY_CHUNK_SIZE):
        query = sa.select([kernels]).slice(chunk, chunk + QUERY_CHUNK_SIZE)
        kernel_rows = connection.execute(query).fetchall()

        # imgs = db_session.query(ImageRow).all()
        # img_map = {img.name: img.id for img in imgs}

        all_kernel_sessions = {}
        # kernel_id and session_id are the same if it is a single kernel session.
        # update kernel's session_id of single kernel session.
        single_kernel_ids = {}
        for row in kernel_rows:
            sess_id = row["session_id"]
            if sess_id not in all_kernel_sessions:
                if sess_id == row["id"]:
                    # create session with new id if the kernel_id and session_id are the same.
                    sess_id = uuid4()
                    single_kernel_ids[row["id"]] = sess_id
                sess = {
                    "id": sess_id,
                    "creation_id": row["session_creation_id"],
                    "name": row["session_name"],
                    "session_type": row["session_type"],
                    "cluster_mode": row["cluster_mode"],
                    "cluster_size": row["cluster_size"],
                    "scaling_group_name": row["scaling_group"],
                    "domain_name": row["domain_name"],
                    "group_id": row["group_id"],
                    "user_uuid": row["user_uuid"],
                    "access_key": row["access_key"],
                    # "image_id": img_map[row["image"]],
                    # "image": row["image"],
                    "tag": row["tag"],
                    "occupying_slots": row["occupied_slots"],
                    "requested_slots": row["occupied_slots"],
                    "vfolder_mounts": row["vfolder_mounts"],
                    "resource_opts": row["resource_opts"],
                    "bootstrap_script": row["bootstrap_script"],
                    "use_host_network": row["use_host_network"],
                    "created_at": row["created_at"],
                    "terminated_at": row["terminated_at"],
                    "starts_at": row["starts_at"],
                    "status": row["status"],
                    # "status_changed": row["status_changed"],
                    "status_history": row["status_history"],
                    "status_info": row["status_info"],
                    "status_data": row["status_data"],
                    "callback_url": row["callback_url"],
                    "startup_command": row["startup_command"],
                    "result": row["result"],
                    "num_queries": row["num_queries"],
                    "last_stat": row["last_stat"],
                }
                all_kernel_sessions[sess_id] = sess
            else:
                sess = all_kernel_sessions[sess_id]

                # st_change = sess["status_changed"]

                try:
                    if sess["created_at"] is not None and row["created_at"] is not None:
                        if sess["created_at"] > row["created_at"]:
                            sess["created_at"] = row["created_at"]
                            # st_change = row["st_change"]
                except (TypeError, ValueError):
                    pass

                try:
                    if sess["starts_at"] is not None and row["starts_at"] is not None:
                        if sess["starts_at"] > row["starts_at"]:
                            sess["starts_at"] = row["starts_at"]
                            # st_change = row["st_change"]
                except (TypeError, ValueError):
                    pass

                # if str(sess["status"]) not in ("ERROR", "CANCELLED"):
                #     if KernelStatus.index(str(sess["status"])) > KernelStatus.index(str(row["status"])):
                #         sess["status"] = row["status"]
                sess["status"] = row["status"]

                try:
                    if sess["terminated_at"] is not None and row["terminated_at"] is not None:
                        if sess["terminated_at"] < row["terminated_at"]:
                            sess["terminated_at"] = row["terminated_at"]
                            # st_change = row["status_changed"]
                    elif sess["terminated_at"] is None:
                        pass
                    elif row["terminated_at"] is None:
                        sess["terminated_at"] = None
                    # sess["status_changed"] = st_change
                except (TypeError, ValueError):
                    pass

                if sess["status_info"] != row["status_info"]:
                    import json

                    sinfo = sess["status_info"]
                    try:
                        sinfo = json.loads(sinfo)
                    except json.decoder.JSONDecodeError:
                        sinfo = {str(sess["id"]): sinfo}
                    sinfo = {**sinfo, str(row["id"]): row["status_info"]}
                    sess["status_info"] = json.dumps(sinfo)

        if all_kernel_sessions:
            creates = tuple(all_kernel_sessions.values())
            connection.execute(SessionRow.__table__.insert(), creates)

        # Session dependency table
        kern_ids = list(single_kernel_ids.keys())
        insert_values = []
        sess_dep_query = sa.select(SessionDependencyRow).where(
            SessionDependencyRow.session_id.in_(kern_ids)
            | SessionDependencyRow.depends_on.in_(kern_ids)
        )
        for row in connection.execute(sess_dep_query).fetchall():
            val = {}
            if row["session_id"] in single_kernel_ids:
                val["session_id"] = single_kernel_ids[row["session_id"]]
            else:
                val["session_id"] = row["session_id"]

            if row["depends_on"] in single_kernel_ids:
                val["depends_on"] = single_kernel_ids[row["depends_on"]]
            else:
                val["depends_on"] = row["depends_on"]
            insert_values.append(val)
        dep_delete_query = sa.delete(SessionDependencyRow).where(
            SessionDependencyRow.session_id.in_(kern_ids)
            | SessionDependencyRow.depends_on.in_(kern_ids)
        )
        connection.execute(dep_delete_query)
        if insert_values:
            connection.execute(sa.insert(SessionDependencyRow), insert_values)

        # Kernel table
        sess_query = (
            sa.update(kernels)
            .where(kernels.c.id == sa.bindparam("kernel_id"))
            .values(session_id=sa.bindparam("b_session_id"))
        )
        sess_update_params = []
        for kern_id, sess_id in single_kernel_ids.items():
            sess_update_params.append(
                {
                    "kernel_id": kern_id,
                    "b_session_id": sess_id,
                }
            )
        if sess_update_params:
            connection.execute(sess_query, sess_update_params)

    op.create_foreign_key(
        op.f("fk_session_dependencies_session_id_sessions"),
        "session_dependencies",
        "sessions",
        ["session_id"],
        ["id"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("fk_session_dependencies_depends_on_sessions"),
        "session_dependencies",
        "sessions",
        ["depends_on"],
        ["id"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        op.f("fk_kernels_session_id_sessions"), "kernels", "sessions", ["session_id"], ["id"]
    )
    op.add_column("kernels", sa.Column("requested_slots", pgsql.JSONB(), nullable=True))

    ## Association tables
    # groups_users
    op.drop_constraint(
        "uq_association_user_id_group_id", "association_groups_users", type_="unique"
    )

    # scaling_groups_domains
    op.drop_constraint("uq_sgroup_domain", "sgroups_for_domains", type_="unique")

    # scaling_groups_groups
    op.drop_constraint("uq_sgroup_ugroup", "sgroups_for_groups", type_="unique")

    # scaling_groups_keypairs
    op.drop_constraint("uq_sgroup_akey", "sgroups_for_keypairs", type_="unique")

    # ### end Alembic commands ###


def downgrade():
    connection = op.get_bind()

    # Kernel table
    op.drop_constraint(op.f("fk_kernels_session_id_sessions"), "kernels", type_="foreignkey")
    kernels = sa.Table(
        "kernels",
        metadata,
        KernelIDColumn(),
        sa.Column("session_id", GUID, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.drop_constraint(
        op.f("fk_session_dependencies_depends_on_sessions"),
        "session_dependencies",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_session_dependencies_session_id_sessions"),
        "session_dependencies",
        type_="foreignkey",
    )
    kernel_cnt = connection.execute(sa.select([sa.func.count()]).select_from(kernels)).scalar()
    for chunk in range(0, kernel_cnt, QUERY_CHUNK_SIZE):
        query = sa.select([kernels]).slice(chunk, chunk + QUERY_CHUNK_SIZE)
        kernel_rows = connection.execute(query).fetchall()

        num_kernel_sess = defaultdict(int)
        sess_kern_map = {}
        for kern in kernel_rows:
            # restore kernel's session_id
            sess_id = kern["session_id"]
            num_kernel_sess[sess_id] += 1
            if sess_id not in sess_kern_map:
                sess_kern_map[sess_id] = kern["id"]
        kern_update_query = (
            sa.update(kernels)
            .where(kernels.c.id == sa.bindparam("kernel_id"))
            .values({kernels.c.session_id: sa.bindparam("session_id")})
        )
        sess_update_params = []
        single_kern_sess = {}
        for sess_id, num_kern in num_kernel_sess.items():
            if num_kern == 1:
                # it is single kernel session.
                # session_id must be same with kernel_id.
                kernel_id = sess_kern_map[sess_id]
                single_kern_sess[sess_id] = kernel_id
                sess_update_params.append(
                    {
                        "kernel_id": kernel_id,
                        "session_id": kernel_id,
                    }
                )
        if sess_update_params:
            connection.execute(kern_update_query, sess_update_params)
        # op.drop_column("kernels", "image_id")
        op.drop_column("kernels", "requested_slots")

        # Session dependency table
        sess_ids = list(single_kern_sess.keys())
        sess_dep_query = sa.select(SessionDependencyRow).where(
            SessionDependencyRow.session_id.in_(sess_ids)
            | SessionDependencyRow.depends_on.in_(sess_ids)
        )
        insert_values = []
        for row in connection.execute(sess_dep_query).fetchall():
            val = {}
            if row["session_id"] in single_kern_sess:
                val["session_id"] = single_kern_sess[row["session_id"]]
            else:
                val["session_id"] = row["session_id"]

            if row["depends_on"] in single_kern_sess:
                val["depends_on"] = single_kern_sess[row["depends_on"]]
            else:
                val["depends_on"] = row["depends_on"]
            insert_values.append(val)
        dep_delete_query = sa.delete(SessionDependencyRow).where(
            SessionDependencyRow.session_id.in_(sess_ids)
            | SessionDependencyRow.depends_on.in_(sess_ids)
        )
        connection.execute(dep_delete_query)
        if insert_values:
            connection.execute(sa.insert(SessionDependencyRow), insert_values)

    op.create_foreign_key(
        "fk_session_dependencies_session_id_kernels",
        "session_dependencies",
        "kernels",
        ["session_id"],
        ["id"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_session_dependencies_depends_on_kernels",
        "session_dependencies",
        "kernels",
        ["depends_on"],
        ["id"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    )

    # Session table
    op.drop_index(op.f("ix_sessions_terminated_at"), table_name="sessions")
    # op.drop_index(op.f("ix_sessions_status_changed"), table_name="sessions")
    # op.drop_index(op.f("ix_sessions_status"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_session_type"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_scaling_group_name"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_result"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_name"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_created_at"), table_name="sessions")
    op.drop_table("sessions")

    # Drop ENUM types
    sess_statues = pgsql.ENUM(
        *session_status,
        name="sessionstatus",
    )
    sess_results = pgsql.ENUM("UNDEFINED", "SUCCESS", "FAILURE", name="sessionresults")

    sess_statues.drop(op.get_bind())
    sess_results.drop(op.get_bind())

    ## Association tables
    # groups users
    op.create_unique_constraint(
        "uq_association_user_id_group_id", "association_groups_users", ["user_id", "group_id"]
    )

    # scaling groups domains
    op.create_unique_constraint(
        "uq_sgroup_domain", "sgroups_for_domains", ["scaling_group", "domain"]
    )

    # scaling_groups_groups
    op.create_unique_constraint(
        "uq_sgroup_ugroup", "sgroups_for_groups", ["scaling_group", "group"]
    )

    # scaling_groups_keypairs
    op.create_unique_constraint(
        "uq_sgroup_akey", "sgroups_for_keypairs", ["scaling_group", "access_key"]
    )

    ### end Alembic commands ###
