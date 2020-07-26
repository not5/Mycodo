# coding=utf-8
from marshmallow_sqlalchemy import ModelSchema

from mycodo.databases import CRUDMixin
from mycodo.databases import set_uuid
from mycodo.mycodo_flask.extensions import db


class Output(CRUDMixin, db.Model):
    __tablename__ = "output"
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, unique=True, primary_key=True)
    unique_id = db.Column(db.String, nullable=False, unique=True, default=set_uuid)  # ID for influxdb entries
    output_type = db.Column(db.Text, default='wired')  # Options: 'command', 'wired', 'wireless_rpi_rf', 'pwm'
    log_level_debug = db.Column(db.Boolean, default=False)
    output_mode = db.Column(db.Text, default=None)  # TODO: Rename to flow_rate_method
    interface = db.Column(db.Text, default='')
    location = db.Column(db.Text, default='')
    name = db.Column(db.Text, default='Output')
    pin = db.Column(db.Integer, default=None)  # Pin connected to the device/output
    on_state = db.Column(db.Boolean, default=True)  # GPIO output to turn output on (True=HIGH, False=LOW)
    amps = db.Column(db.Float, default=0.0)  # The current drawn by the device connected to the output
    on_until = db.Column(db.DateTime, default=None)  # Stores time to turn off output (if on for a duration)
    off_until = db.Column(db.DateTime, default=None)  # Stores time the output can turn on again
    last_duration = db.Column(db.Float, default=None)  # Stores the last on duration (seconds)
    on_duration = db.Column(db.Boolean, default=None)  # Stores if the output is currently on for a duration
    protocol = db.Column(db.Integer, default=None)
    pulse_length = db.Column(db.Integer, default=None)
    linux_command_user = db.Column(db.Text, default=None)
    on_command = db.Column(db.Text, default=None)
    off_command = db.Column(db.Text, default=None)
    pwm_command = db.Column(db.Text, default=None)
    force_command = db.Column(db.Boolean, default=False)
    trigger_functions_at_start = db.Column(db.Boolean, default=True)

    state_startup = db.Column(db.Text, default=None)
    startup_value = db.Column(db.Float, default=0)
    state_shutdown = db.Column(db.Text, default=None)
    shutdown_value = db.Column(db.Float, default=0)

    # I2C
    i2c_location = db.Column(db.Text, default=None)  # Address location for I2C communication
    i2c_bus = db.Column(db.Integer, default='')  # I2C bus the sensor is connected to

    # FTDI
    ftdi_location = db.Column(db.Text, default=None)  # Device location for FTDI communication

    # Communication (SPI)
    uart_location = db.Column(db.Text, default=None)  # Device location for UART communication
    baud_rate = db.Column(db.Integer, default=None)  # Baud rate for UART communication

    # PWM
    pwm_hertz = db.Column(db.Integer, default=None)  # PWM Hertz
    pwm_library = db.Column(db.Text, default=None)  # Library to produce PWM
    pwm_invert_signal = db.Column(db.Boolean, default=False)  # 90% duty cycle would become 10%

    # Atlas EZO-PMP
    flow_rate = db.Column(db.Float, default=None)  # example: ml per minute

    custom_options = db.Column(db.Text, default='')

    # TODO: Remove because no longer used
    # measurement = db.Column(db.Text, default=None)
    # unit = db.Column(db.Text, default=None)
    # channel = db.Column(db.Integer, default=None)
    # conversion_id = db.Column(db.Text, db.ForeignKey('conversion.unique_id'), default='')

    def __repr__(self):
        return "<{cls}(id={s.id})>".format(s=self, cls=self.__class__.__name__)

    def is_setup(self):
        """
        This function checks to see if the GPIO pin is setup and ready to use.  This is for safety
        and to make sure we don't blow anything.

        # TODO Make it do that.

        :return: Is it safe to manipulate this output?
        :rtype: bool
        """
        if self.output_type == 'wired' and self.pin:
            self.setup_pin()
            return True

    def setup_pin(self):
        """
        Setup pin for this output

        :rtype: None
        """
        try:
            from RPi import GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(True)
            GPIO.setup(self.pin, GPIO.OUT)
        except:
            print("RPi.GPIO and Raspberry Pi required for this action")


class OutputSchema(ModelSchema):
    class Meta:
        model = Output
