
# developed by Gabi Zapodeanu, TSA, GPO, Cisco Systems

# !/usr/bin/env python3

# This file includes declarations required for SparkConnect.py
# Change the values to your lab environment
# The lab will require PI, CMX, API-EM, and access to Cisco Spark


PI_URL = 'https://172.16.11.25'
PI_USER = 'python'
PI_PASSW = 'Clive.17'
WLAN_DEPLOY = 'SparkConnect'
WLAN_DISABLE = 'DisableSparkConnect'
APGROUP_TEMPLATE = 'clive'

EM_URL = 'https://172.16.11.30/api/v1'
EM_USER = 'python'
EM_PASSW = 'Clive.17'

# CMX_URL = 'https://172.16.11.27/'
CMX_URL = 'https://cmxlocationsandbox.cisco.com/'
# CMX_USER = 'python'
CMX_USER = 'learning'
# CMX_PASSW = 'Clive!17'
CMX_PASSW = 'learning'

SPARK_URL = 'https://api.ciscospark.com/v1'
SPARK_AUTH = 'Bearer ' + 'Put your Spark Token here'
ROOM_NAME = '{Spark:Connect}'
IT_ENG_EMAIL = 'gabriel.zapodeanu@gmail.com'

WIFI_SSID = 'CLIVE'

