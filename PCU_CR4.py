#!/usr/bin/python3

import os
import struct
from textwrap import wrap
import argparse
import bitstruct

from useful_stuff import *


###################################################################################################
#
#  5. PCU CR4 registers (bus:B31, device:30, function: 4)
#     External Design Specification vol 2 : Registers, §18.5 page 5816
#
###################################################################################################
def decode_VID_1_30_4_CFG(reg):
  comment="assigned by PCI-SIG to Intel"  
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  vendor_id = bitstruct.unpack("u16", reg)[0]
  if vendor_id==0x8086:
    return "{0}\t\t{1}".format( bold(green("INTEL")), blue(comment) )
  else:
    return "Unknown\t\t"+blue(comment)   


def decode_SVID_1_30_4_CFG(reg):
  comment="specifies Intel® but can be set to any value once after reset"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  vendor_id = bitstruct.unpack("u16", reg)[0]
  if vendor_id==0x8086:
    return "{0}\t\t{1}".format( bold(green("INTEL")), blue(comment) )
  else:
    return "Unknown\t\t"+blue(comment)   


def decode_CONFIG_TDP_LEVEL1(reg):
  comment="Level 1 configurable TDP settings"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,pkg_min_pwr,pkg_max_pwr,_,tdp_ratio,_,pkg_tdp= \
    bitstruct.unpack("b1 u16 u15 u8 u8 b1 u15", reg)
  ro=red("RO")  
  line0="\t\t{0}\n".format(blue(comment))
  value="{0}".format(pkg_min_pwr*pcu["pwr_unit"])         
  line1="  \u251C {0} PKG MIN PWR = {1} W\t\t{2}\n".format(
           ro, yellow(value), 
           blue("Min pkg power setting allowed for this level") )
  value="{0}".format(pkg_max_pwr*pcu["pwr_unit"])         
  line2="  \u251C {0} PKG MAX PWR = {1} W\t\t{2}\n".format( 
           ro, yellow(value), blue("Max power setting allowed in this level") )
  value="{0}".format(tdp_ratio)         
  line3="  \u251C {0} TDP RATIO   = {1}\n".format( ro, yellow(value) )
  value="{0:3.0f}".format(pkg_tdp*pcu["pwr_unit"])         
  line4="  \u2514 {0} PKG TDP     = {1} W\t\t{2}".format(
           ro, yellow(value), blue("Power for this TDP level") )
  return line0+line1+line2+line3+line4


def decode_MCP_THERMAL_REPORT_2_CFG(reg):
  comment="the hottest absolute temp. of any component in the multi-chip package"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  package_absolute_max_temperature_high,package_absolute_max_temperature_low = \
     bitstruct.unpack("p16 u10 s6", reg)
  ro=red("RO")  
  return "{0} {1}\t{2}".format(package_absolute_max_temperature_high,
                               package_absolute_max_temperature_low,blue(comment))


def decode_UNC_TSC_SNAPSHOT(reg):
  comment="Value of the captured Uncore TSC on internal rising edge of TSC_SYNC"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  uncore_tsc_snapshot= bitstruct.unpack("p1 u63", reg)[0]
  ro=red("RO")  
  hexa="{0:08X}".format(uncore_tsc_snapshot)
  return "{0} {1}h\t{2}".format(ro, blue(hexa), blue(comment))


def decode_TSC_HP_OFFSET(reg):
  comment="BIOS may write here to update the TSC in the hot plugged socket"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  tsc_update,tsc_offset= bitstruct.unpack("b1 u63", reg)
  ro=red("RO")  
  if tsc_update:
    tsc=green("SET")
  else:
    tsc=yellow("not SET")
  line0="\t\t{0}\n".format(blue(comment))
  line1="  \u251C {0} TSC UPDATE = {1}\t\t{2}\n".format(
        ro, tsc, blue("When set, will add the TSC_OFFSET value to the Uncore TSC"))
  value="{0}".format(tsc_offset)         
  line2="  \u2514 {0} TSC OFFSET = {1}°C\t\t\t{2}".format(
        ro, yellow(value), blue("update to the Uncore TSC to align it for Hot Plug"))
  return line0+line1+line2


def decode_FLEX_RATIO(reg):
  comment="The Flexible Boot register is written by BIOS in order to modify the maximum "\
          "nonturbo ratio on the next reset. The DP/MP systems use this FLEX_RATIO in this "\
          "register to configure the maximum common boot ratio for all physical processors "\
          "in the system. The value in the FLEX_RATIO take effect on the next reset based on "\
          "the value of FLEX_EN"
  wrapped=wrap(comment, 65)
  blued=[ blue(s) for s in wrapped ]
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,oc_lock,oc_bins,enable,flex_ratio,oc_extra_voltage = \
          bitstruct.unpack("u43 b1 u3 b1 u8 u8", reg)
  ro=red("RO")  
  if oc_lock:
    line1="  \u251C "+ro+" OVERCLOCKING LOCK = " + red("LOCKED") + \
          "\t"+blue("the overclocking bitfields is locked from further writes")+"\n"
  else:
    line1="  \u251C "+ro+" OVERCLOCKING LOCK = " + green("UNLOCKED")+"\n"
  value="{0}".format(oc_bins)
  line2="  \u251C {0} OVERCLOCKING BINS = {1}\t\t{2}\n".format(
        ro, yellow(value), blue("The maximum number of bins by which the part can be overclocked") )
  if enable:
    enable=green("ENABLED")
    comment="FLEX_RATIO will be used to override the max non-turbo ratio on next reboot"
  else:  
    enable=red("DISABLED")
    comment="all writes to FLEX_RATIO will be ignored"
  line0="\t\t"+blued[0]+"\n"+"\n".join(["  \u2502"+"\t"*5+s for s in blued[1:]])+"\n"  
  line3="  \u251C {0} FLEX RATIO is {1}\t\t{2}\n".format(ro, enable, blue(comment))
  value="{0}".format(flex_ratio)
  line4="  \u251C {0} FLEX RATIO        = {1}\t\t{2}\n".format(
        ro, yellow(value), blue("maximum non-turbo ratio <= maximum ratio of hardware"))
  value="{0}".format(oc_extra_voltage/256*1000)
  line5="  \u2514 {0} EXTRA VOLTAGE     = {1} mV\t{2}".format(
        ro, yellow(value), blue("Extra voltage to be used for overclocking"))
  return line0+line1+line2+line3+line4+line5


registers= [
  (0x00, "vendor ID"                , 2, decode_VID_1_30_4_CFG ),
  (0x02, "Device ID"                , 2, "RO 325Ah assigned by each IP/function owner as a unique identifier"),
  (0x04, "PCI Command"              , 2, "mostly hardwired to 0"),
  (0x06, "PCI status"               , 2, ""),
  (0x08, "Rev ID & Class code reg." , 8, ""),
  (0x0C, "CACHE LINE SIZE REGISTER" , 1, "size of cache line"),
  (0x0D, "PCI LATENCY TIMER"        , 1, "Not applicable to PCIe. Hardwired to 0"),
  (0x0E, "HEADER TYPE"              , 1, "PCI header type : multi function device, type 0 header"),
  (0x0F, "BUILT IN SELF TEST"       , 1, "Not supported. Hardwired to 0"),
  (0x2C, "Subsystem vendor ID"      , 2, decode_SVID_1_30_4_CFG),
  (0x2E, "Subsystem ID"             , 2, "Assigned to uniquely identify the subsystem"),
  (0x34, "Capability pointer"       , 1, "Points to the first capability structure : the PCIe capability"),
  (0x3C, "Interrupt line"           , 1, "N/A for PCU"),
  (0x3D, "Interrupt pin"            , 1, "N/A for PCU"),
  (0x3E, "Minimum grant"            , 1, "PCI min grant reg : PCU doesn't burst as a PCI compliant master"),
  (0x3F, "Maximum latency"          , 1, "PCU has no specific requirements for how often it accesses PCI"),
  (0x80, "GLOBAL NID SOCKET 4to7 MAP", 4, ""),
  (0x84, "VIRAL CONTROL CFG"        , 4, ""),
  (0x88, "PCU FIRST RMCA TSC LO"    , 4, ""),
  (0x8C, "PCU FIRST RMCA TSC HI"    , 4, ""),
  (0xA0, "MEM ACCUMULATED BW CH CFG0", 4, ""),
  (0xA4, "MEM ACCUMULATED BW CH CFG1", 4, ""),
  (0xA8, "MEM ACCUMULATED BW CH CFG2", 4, ""),
  (0xAC, "MEM ACCUMULATED BW CH CFG3", 4, ""),
  (0xB0, "MEM ACCUMULATED BW CH CFG4", 4, ""),
  (0xB4, "MEM ACCUMULATED BW CH CFG5", 4, ""),
  (0xB8, "MEM ACCUMULATED BW CH CFG6", 4, ""),
  (0xBC, "MEM ACCUMULATED BW CH CFG7", 4, ""),
  (0xC0, "MEM ACCUMULATED BW CH CFG8", 4, ""),
  (0xC4, "MEM ACCUMULATED BW CH CFG9", 4, ""),
  (0xC8, "MEM ACCUMULATED BW CH CFG10", 4, ""),
  (0xCC, "MEM ACCUMULATED BW CH CFG11", 4, ""),
  (0xD0, "MCP THERMAL REPORT 1"     , 4, ""),
  (0xD8, "MCP THERMAL REPORT 2"     , 4, decode_MCP_THERMAL_REPORT_2_CFG),
  (0xE0, "UNCORE TSC SNAPSHOT"      , 8, decode_UNC_TSC_SNAPSHOT),
  (0xE8, "TSC HP OFFSET REGISTER"   , 8, decode_TSC_HP_OFFSET),
  (0xF0, "PCU FIRST IERR TSC LO"    , 4, "Low  4B of TSC snapshot taken on first internal IERR"),
  (0xF4, "PCU FIRST IERR TSC HI"    , 4, "High 4B of TSC snapshot taken on first internal IERR"),
  (0xF8, "PCU FIRST MCERR TSC LO"   , 4, "Low  4B of TSC snapshot taken on first internal MCERR"),
  (0xFC, "PCU FIRST MCERR TSC HI"   , 4, "High 4B of TSC snapshot taken on first internal MCERR"),
]
