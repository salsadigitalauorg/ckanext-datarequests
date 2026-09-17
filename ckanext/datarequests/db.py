# -*- coding: utf-8 -*-

# Copyright (c) 2015-2016 CoNWeT Lab., Universidad Politécnica de Madrid

# This file is part of CKAN Data Requests Extension.

# CKAN Data Requests Extension is free software: you can redistribute it and/or
# modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# CKAN Data Requests Extension is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with CKAN Data Requests Extension. If not, see <http://www.gnu.org/licenses/>.

import sqlalchemy as sa
import uuid
import logging

from ckan import model
from ckan.model.meta import metadata
# CDP: current_user and h for the Visible rules in get_ordered_by_date.
from ckan.plugins.toolkit import current_user, h
from ckanext.datarequests import constants

from sqlalchemy import func
# Fork, not CDP: SQLAlchemy 2.0 moved declarative_base to sqlalchemy.orm.
from sqlalchemy.orm import declarative_base
# CDP: case pins the user's own requests first.
from sqlalchemy.sql import case
from sqlalchemy.sql.expression import or_

from . import common

log = logging.getLogger(__name__)

Base = declarative_base(metadata=metadata)


def uuid4():
    return str(uuid.uuid4())


closing_circumstances_enabled = common.get_config_bool_value('ckan.datarequests.enable_closing_circumstances', False)

datarequests_table = sa.Table('datarequests', metadata,
                              sa.Column('user_id', sa.types.UnicodeText, primary_key=False, default=u''),
                              sa.Column('id', sa.types.UnicodeText, primary_key=True, default=uuid4),
                              sa.Column('title', sa.types.Unicode(constants.NAME_MAX_LENGTH), primary_key=True, default=u''),
                              sa.Column('description', sa.types.Unicode(constants.DESCRIPTION_MAX_LENGTH), primary_key=False, default=u''),
                              sa.Column('organization_id', sa.types.UnicodeText, primary_key=False, default=None),
                              sa.Column('open_time', sa.types.DateTime, primary_key=False, default=None),
                              sa.Column('accepted_dataset_id', sa.types.UnicodeText, primary_key=False, default=None),
                              sa.Column('close_time', sa.types.DateTime, primary_key=False, default=None),
                              sa.Column('closed', sa.types.Boolean, primary_key=False, default=False),
                              sa.Column('close_circumstance', sa.types.Unicode(constants.CLOSE_CIRCUMSTANCE_MAX_LENGTH), primary_key=False, default=u'')
                              if closing_circumstances_enabled else None,
                              sa.Column('approx_publishing_date', sa.types.DateTime, primary_key=False, default=None)
                              if closing_circumstances_enabled else None,
                              # CDP: the extra form fields, Status, the requested dataset, and State for soft delete.
                              sa.Column('data_use_type', sa.types.Unicode(constants.MAX_LENGTH_255), primary_key=False, default=u''),
                              sa.Column('who_will_access_this_data', sa.types.Unicode(constants.DESCRIPTION_MAX_LENGTH), primary_key=False, default=u''),
                              sa.Column('requesting_organisation', sa.types.Unicode(constants.MAX_LENGTH_255), primary_key=False, default=u''),
                              sa.Column('data_storage_environment', sa.types.Unicode(constants.DESCRIPTION_MAX_LENGTH), primary_key=False, default=u''),
                              sa.Column('data_outputs_type', sa.types.Unicode(constants.MAX_LENGTH_255), primary_key=False, default=u''),
                              sa.Column('data_outputs_description', sa.types.Unicode(constants.DESCRIPTION_MAX_LENGTH), primary_key=False, default=u''),
                              sa.Column('status', sa.types.Unicode(constants.MAX_LENGTH_255), primary_key=False, default=u'Assigned'),
                              sa.Column('requested_dataset', sa.types.Unicode(constants.MAX_LENGTH_255), primary_key=False, default=u''),
                              sa.Column('state', sa.types.UnicodeText, default=model.core.State.ACTIVE),
                              # CDP: end
                              extend_existing=True,
                              )

comments_table = sa.Table('datarequests_comments', metadata,
                          sa.Column('id', sa.types.UnicodeText, primary_key=True, default=uuid4),
                          sa.Column('user_id', sa.types.UnicodeText, primary_key=False, default=u''),
                          sa.Column('datarequest_id', sa.types.UnicodeText, primary_key=True, default=uuid4),
                          sa.Column('time', sa.types.DateTime, primary_key=True, default=u''),
                          sa.Column('comment', sa.types.Unicode(constants.COMMENT_MAX_LENGTH), primary_key=False, default=u''),
                          extend_existing=True
                          )

followers_table = sa.Table('datarequests_followers', metadata,
                           sa.Column('id', sa.types.UnicodeText, primary_key=True, default=uuid4),
                           sa.Column('user_id', sa.types.UnicodeText, primary_key=False, default=u''),
                           sa.Column('datarequest_id', sa.types.UnicodeText, primary_key=True, default=uuid4),
                           sa.Column('time', sa.types.DateTime, primary_key=True, default=u''),
                           extend_existing=True
                           )


# CDP: soft delete. Every query below filters on _active.
def _active(cls):
    # Rows created before the state column existed are null and count as active.
    return or_(cls.state == model.core.State.ACTIVE, cls.state.is_(None))


# CDP: StatefulObjectMixin gives delete() and State for soft delete.
class DataRequest(model.core.StatefulObjectMixin, model.DomainObject, Base):

    __table__ = datarequests_table

    @classmethod
    def get(cls, **kw):
        '''Finds all the instances required.'''
        query = model.Session.query(cls).autoflush(False)
        query = query.filter(_active(cls))
        return query.filter_by(**kw).all()

    @classmethod
    def datarequest_exists(cls, title):
        '''Returns true if there is a Data Request with the same title (case insensitive)'''
        query = model.Session.query(cls).autoflush(False)
        query = query.filter(_active(cls))
        return query.filter(func.lower(cls.title) == func.lower(title)).first() is not None

    @classmethod
    def get_ordered_by_date(cls, organization_id=None, user_id=None, closed=None, q=None, desc=False, status=None, state=None):
        '''Personalized query'''
        query = model.Session.query(cls).autoflush(False)
        # CDP: soft delete; status and state parameters added to the signature.
        if state is None:
            query = query.filter(_active(cls))
        else:
            query = query.filter_by(state=state)
        # CDP: end

        params = {}

        if organization_id is not None:
            params['organization_id'] = organization_id

        if user_id is not None:
            params['user_id'] = user_id

        if closed is not None:
            params['closed'] = closed

        # CDP: Status filter.
        if status is not None:
            params['status'] = status

        if q is not None:
            search_expr = '%{0}%'.format(q)
            query = query.filter(or_(cls.title.ilike(search_expr), cls.description.ilike(search_expr)))

        query = query.filter_by(**params)

        order_by_filter = cls.open_time.desc() if desc else cls.open_time.asc()

        # CDP: the Visible rules and own-requests-first ordering, to the end of this method.
        # Sysadmins see every request. Everyone else sees their own plus those
        # of organisations they belong to.
        if not current_user.sysadmin:
            current_user_orgs = h.organizations_available('read') or []
            member_org_ids = [org['id'] for org in current_user_orgs]

            if organization_id is None:
                query = query.filter(or_(cls.user_id == current_user.id, cls.organization_id.in_(member_org_ids)))
            elif organization_id not in member_org_ids:
                query = query.filter(cls.user_id == current_user.id)
            else:
                query = query.filter(or_(cls.user_id == current_user.id, cls.organization_id == organization_id))

        current_user_id = current_user.id if current_user else None
        if current_user_id:
            # Pin the current user's own requests to the top of the list.
            current_user_order = case(
                (cls.user_id == current_user_id, 1),
                else_=0
            ).label('current_user_order')

            query = query.order_by(current_user_order.desc(), order_by_filter)
        else:
            query = query.order_by(order_by_filter)

        return query.all()
        # CDP: end

    @classmethod
    def get_open_datarequests_number(cls):
        '''Returns the number of data requests that are open'''
        return model.Session.query(func.count(cls.id)).filter_by(closed=False).filter(_active(cls)).scalar()


class Comment(model.DomainObject, Base):

    __table__ = comments_table

    @classmethod
    def get(cls, **kw):
        '''Finds all the instances required.'''
        query = model.Session.query(cls).autoflush(False)
        return query.filter_by(**kw).all()

    @classmethod
    def get_ordered_by_date(cls, datarequest_id, desc=False):
        '''Personalized query'''
        query = model.Session.query(cls).autoflush(False)
        order_by_filter = cls.time.desc() if desc else cls.time.asc()
        return query.filter_by(datarequest_id=datarequest_id).order_by(order_by_filter).all()

    @classmethod
    def get_comment_datarequests_number(cls, **kw):
        '''
        Returned the number of comments of a data request
        '''
        return model.Session.query(func.count(cls.id)).filter_by(**kw).scalar()


class DataRequestFollower(model.DomainObject, Base):

    __table__ = followers_table

    @classmethod
    def get(cls, **kw):
        '''Finds all the instances required.'''
        query = model.Session.query(cls).autoflush(False)
        return query.filter_by(**kw).all()

    @classmethod
    def get_datarequest_followers_number(cls, **kw):
        '''
        Returned the number of followers of a data request
        '''
        return model.Session.query(func.count(cls.id)).filter_by(**kw).scalar()


def init_db(deprecated_model=None):

    # Fork, not CDP: only create this extension's tables.
    metadata.create_all(model.meta.engine, tables=[datarequests_table, comments_table, followers_table])

    update_db()


# Fork, not CDP: rewritten to inspect the live schema, because upstream's check
# against the declared metadata never finds a missing column.
def update_db(deprecated_model=None):
    '''
    Add columns introduced after the datarequests table was first created.

    The declared metadata always contains every column, so the live schema is
    inspected instead.
    '''
    engine = model.Session.get_bind()
    inspector = sa.inspect(engine)
    if not inspector.has_table('datarequests'):
        return

    columns = {column['name']: column for column in inspector.get_columns('datarequests')}

    new_columns = []
    if closing_circumstances_enabled:
        new_columns += [
            ('close_circumstance', 'varchar({0}) NULL'.format(constants.CLOSE_CIRCUMSTANCE_MAX_LENGTH)),
            ('approx_publishing_date', 'timestamp NULL'),
        ]
    # CDP: columns this fork adds.
    new_columns += [
        ('data_use_type', 'varchar(255) NULL'),
        ('who_will_access_this_data', 'character varying(1000) NULL'),
        ('requesting_organisation', 'text'),
        ('data_storage_environment', 'character varying(1000) NULL'),
        ('data_outputs_type', 'varchar(255) NULL'),
        ('data_outputs_description', 'character varying(1000) NULL'),
        ('status', 'varchar(255) NULL'),
        ('requested_dataset', 'text'),
        ('state', 'text'),
    ]
    # CDP: end

    with engine.begin() as connection:
        for name, column_type in new_columns:
            if name not in columns:
                log.info("DataRequests-UpdateDB: '%s' field does not exist, adding...", name)
                connection.execute(sa.DDL('ALTER TABLE "datarequests" ADD COLUMN "{0}" {1}'.format(name, column_type)))

        # CDP: widen title to NAME_MAX_LENGTH.
        if 'title' in columns and getattr(columns['title']['type'], 'length', None) == 100:
            log.info("DataRequests-UpdateDB: 'title' field length is 100, changing to %d...", constants.NAME_MAX_LENGTH)
            connection.execute(sa.DDL('ALTER TABLE "datarequests" ALTER COLUMN "title" TYPE varchar({0})'.format(constants.NAME_MAX_LENGTH)))
