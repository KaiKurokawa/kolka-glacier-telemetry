from ..codebase.helpers.xml_parser import parse_telemetry_xml

xml_content = """<?xml version="1.0" encoding="utf-8"?>
<message>
  <report TIME="2026-09-29T15:00:00">
    <station ID="77777" LAT="55.8623" LON="37.4857" Z="0" />
    <parameter VAR="WS" Z="10M" T="10M" STATUS="0">
      <value PROC="AVE">0.3</value>
      <value PROC="MAX">0.5</value>
    </parameter>
    <parameter VAR="WD" Z="10M" TYPE="0" PROC="AVE" T="10M" STATUS="0">147</parameter>
    <parameter VAR="TA" Z="2M" T="10M" STATUS="0">
      <value PROC="AVE">13.4</value>
      <value PROC="MAX">13.4</value>
      <value PROC="MIN">13.3</value>
    </parameter>
    <parameter VAR="RH" Z="2M" PROC="AVE" T="10M" STATUS="0">65</parameter>
    <parameter VAR="AP" PROC="AVE" T="10M" STATUS="0" Z="STN">1011.6</parameter>
    <parameter VAR="AP" PROC="AVE" T="10M" STATUS="0" Z="MSL">1033.4</parameter>
    <parameter VAR="LB" PROC="INS" T="10M">45.2</parameter>
    <parameter VAR="PI" Z="2M" PROC="AVE" T="10M" TYPE="L" STATUS="0">0.0</parameter>
    <parameter VAR="P" T="10M" STATUS="0">
      <value PROC="SUM">//</value>
      <value PROC="ACC">0.0</value>
    </parameter>
    <parameter VAR="HS" T="10M">
      <value PROC="INS">90.8</value>
      <value PROC="AVE" T="10M">92.2</value>
      <value PROC="MAX" T="10M">96.9</value>
      <value PROC="MIN" T="10M">88.9</value>
    </parameter>
  </report>
</message>"""

records = parse_telemetry_xml(xml_content)

for record in records:
    for key, value in record.items():
        print(f"{key:50s} = {value!r}")
