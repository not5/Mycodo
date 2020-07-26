# -*- coding: utf-8 -*-
#
# forms_dashboard.py - Dashboard Flask Forms
#

from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms import BooleanField
from wtforms import DecimalField
from wtforms import IntegerField
from wtforms import SelectField
from wtforms import SelectMultipleField
from wtforms import StringField
from wtforms import SubmitField
from wtforms import validators
from wtforms import widgets
from wtforms.validators import DataRequired
from wtforms.widgets.html5 import NumberInput

from mycodo.config_translations import TRANSLATIONS
from mycodo.config import DASHBOARD_WIDGETS


class DashboardBase(FlaskForm):
    dashboard_id = StringField('Dashboard ID', widget=widgets.HiddenInput())
    widget_id = StringField('Widget ID', widget=widgets.HiddenInput())
    widget_type = SelectField('Dashboard Widget Type',
        choices=DASHBOARD_WIDGETS,
        validators=[DataRequired()]
    )
    name = StringField(
        TRANSLATIONS['name']['title'],
        validators=[DataRequired()]
    )
    font_em_name = DecimalField(TRANSLATIONS['font_em_name']['title'])
    refresh_duration = IntegerField(
        TRANSLATIONS['refresh_duration']['title'],
        validators=[validators.NumberRange(
            min=1,
            message=TRANSLATIONS['refresh_duration']['title']
        )],
        widget=NumberInput()
    )
    enable_drag_handle = BooleanField(lazy_gettext('Enable Drag Handle'))
    create = SubmitField(TRANSLATIONS['create']['title'])
    modify = SubmitField(TRANSLATIONS['save']['title'])
    delete = SubmitField(TRANSLATIONS['delete']['title'])


class DashboardConfig(FlaskForm):
    dashboard_id = StringField('Dashboard ID', widget=widgets.HiddenInput())
    name = StringField(
        TRANSLATIONS['name']['title'],
        validators=[DataRequired()]
    )
    dash_modify = SubmitField(TRANSLATIONS['save']['title'])
    dash_delete = SubmitField(TRANSLATIONS['delete']['title'])


class DashboardGraph(FlaskForm):
    math_ids = SelectMultipleField(lazy_gettext('Maths'))
    note_tag_ids = SelectMultipleField(lazy_gettext('Note Tags'))
    pid_ids = SelectMultipleField(lazy_gettext('PIDs'))
    output_ids = SelectMultipleField(lazy_gettext('Outputs'))
    input_ids = SelectMultipleField(lazy_gettext('Inputs'))
    xaxis_duration = IntegerField(
        lazy_gettext('X-Axis (minutes)'),
        validators=[validators.NumberRange(
            min=1,
            message=lazy_gettext("Number of minutes to display of past "
                                 "measurements.")
        )],
        widget=NumberInput()
    )
    enable_header_buttons = BooleanField(lazy_gettext('Enable Header Buttons'))
    enable_auto_refresh = BooleanField(lazy_gettext('Enable Auto Refresh'))
    enable_xaxis_reset = BooleanField(lazy_gettext('Enable X-Axis Reset'))
    enable_title = BooleanField(lazy_gettext('Enable Title'))
    enable_navbar = BooleanField(lazy_gettext('Enable Navbar'))
    enable_export = BooleanField(lazy_gettext('Enable Export'))
    enable_rangeselect = BooleanField(lazy_gettext('Enable Range Selector'))
    enable_graph_shift = BooleanField(lazy_gettext('Enable Graph Shift'))
    enable_manual_y_axis = BooleanField(lazy_gettext('Enable Manual Y-Axis Min/Max'))
    enable_align_ticks = BooleanField(lazy_gettext('Enable Y-Axis Align Ticks'))
    enable_start_on_tick = BooleanField(lazy_gettext('Enable Y-Axis Start On Tick'))
    enable_end_on_tick = BooleanField(lazy_gettext('Enable Y-Axis End On Tick'))
    use_custom_colors = BooleanField(lazy_gettext('Enable Custom Colors'))


class DashboardGauge(FlaskForm):
    gauge_type = SelectField(
        lazy_gettext('Gauge Type'),
        choices=[
            ('gauge_angular', lazy_gettext('Angular Gauge')),
            ('gauge_solid', lazy_gettext('Solid Gauge'))
        ],
        validators=[DataRequired()]
    )
    input_ids = StringField(TRANSLATIONS['measurement']['title'])
    y_axis_min = DecimalField(
        lazy_gettext('Gauge Min'),
        widget=NumberInput(step='any'))
    y_axis_max = DecimalField(
        lazy_gettext('Gauge Max'),
        widget=NumberInput(step='any'))
    max_measure_age = IntegerField(
        TRANSLATIONS['max_age']['title'],
        widget=NumberInput())
    enable_timestamp = BooleanField(lazy_gettext('Show Timestamp'))
    stops = IntegerField(
        TRANSLATIONS['stops']['title'],
        widget=NumberInput())


class DashboardIndicator(FlaskForm):
    measurement_id = StringField(TRANSLATIONS['measurement']['title'])
    max_measure_age = IntegerField(
        TRANSLATIONS['max_age']['title'],
        widget=NumberInput())
    font_em_value = DecimalField(
        lazy_gettext('Value Font (em)'),
        widget=NumberInput(step='any'))
    font_em_timestamp = DecimalField(
        lazy_gettext('Timestamp Font (em)'),
        widget=NumberInput(step='any'))
    enable_timestamp = BooleanField(lazy_gettext('Show Timestamp'))
    option_invert = BooleanField(TRANSLATIONS['invert']['title'])


class DashboardMeasurement(FlaskForm):
    measurement_id = StringField(TRANSLATIONS['measurement']['title'])
    max_measure_age = IntegerField(
        TRANSLATIONS['max_age']['title'],
        widget=NumberInput())
    font_em_value = DecimalField(
        lazy_gettext('Value Font (em)'),
        widget=NumberInput(step='any'))
    font_em_timestamp = DecimalField(
        lazy_gettext('Timestamp Font (em)'),
        widget=NumberInput(step='any'))
    decimal_places = IntegerField(
        lazy_gettext('Decimal Places'),
        widget=NumberInput())
    enable_name = BooleanField(lazy_gettext('Show Name'))
    enable_channel = BooleanField(lazy_gettext('Show Channel'))
    enable_unit = BooleanField(lazy_gettext('Show Unit'))
    enable_measurement = BooleanField(lazy_gettext('Show Measurement'))
    enable_timestamp = BooleanField(lazy_gettext('Show Timestamp'))


class DashboardOutput(FlaskForm):
    output_id = StringField(TRANSLATIONS['output']['title'])
    max_measure_age = IntegerField(
        TRANSLATIONS['max_age']['title'],
        widget=NumberInput())
    font_em_value = DecimalField(
        lazy_gettext('Value Font (em)'),
        widget=NumberInput(step='any'))
    font_em_timestamp = DecimalField(
        lazy_gettext('Timestamp Font (em)'),
        widget=NumberInput(step='any'))
    decimal_places = IntegerField(
        lazy_gettext('Decimal Places'),
        widget=NumberInput())
    enable_status = BooleanField(lazy_gettext('Show Status'))
    enable_value = BooleanField(lazy_gettext('Show Value'))
    enable_unit = BooleanField(lazy_gettext('Show Unit'))
    enable_timestamp = BooleanField(lazy_gettext('Show Timestamp'))
    enable_output_controls = BooleanField(lazy_gettext('Feature Output Controls'))


class DashboardPIDControl(FlaskForm):
    pid_id = StringField(lazy_gettext('PID'))
    max_measure_age = IntegerField(
        TRANSLATIONS['max_age']['title'],
        widget=NumberInput())
    font_em_value = DecimalField(
        lazy_gettext('Value Font (em)'),
        widget=NumberInput(step='any'))
    font_em_timestamp = DecimalField(
        lazy_gettext('Timestamp Font (em)'),
        widget=NumberInput(step='any'))
    camera_max_age = IntegerField(
        TRANSLATIONS['max_age']['title'],
        widget=NumberInput())
    decimal_places = IntegerField(
        lazy_gettext('Decimal Places'),
        widget=NumberInput())
    enable_status = BooleanField(lazy_gettext('Show Status'))
    enable_timestamp = BooleanField(lazy_gettext('Show Timestamp'))
    show_pid_info = BooleanField(lazy_gettext('Show PID Information'))
    show_set_setpoint = BooleanField(lazy_gettext('Show Set Setpoint'))


class DashboardCamera(FlaskForm):
    camera_id = StringField(lazy_gettext('Camera'))
    camera_image_type = StringField(lazy_gettext('Image Display Type'))
    camera_max_age = IntegerField(
        TRANSLATIONS['max_age']['title'],
        widget=NumberInput())
