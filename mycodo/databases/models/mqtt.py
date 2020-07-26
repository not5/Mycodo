# -*- coding: utf-8 -*-
from mycodo.mycodo_flask.extensions import db
from mycodo.databases import CRUDMixin


class MQTT(CRUDMixin, db.Model):
    __tablename__ = "mqtt"
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, unique=True, primary_key=True)
    hostname = db.Column(db.Text, default='localhost')
    port = db.Column(db.Integer, default=1883)
    user = db.Column(db.Text, default='mycodo')
    passw = db.Column(db.Text, default='password')
    clientid = db.Column(db.Text, default='mycodo')
    keep_alive = db.Column(db.Integer, default=60)
    message_count = db.Column(db.Integer, default=0)

    def __repr__(self):
        return "<{cls}(id={s.id})>".format(s=self, cls=self.__class__.__name__)
