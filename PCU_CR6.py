#!/usr/bin/python3

import os
import struct
from textwrap import wrap
import argparse
import bitstruct

from useful_stuff import *


###################################################################################################
#
#  5. PCU CR6 registers (bus:B31, device:30, function: 6)
#     External Design Specification vol 2 : Registers, §18.7 page 5850
#
###################################################################################################
def decode_VID_1_30_6_CFG(reg):
  comment="assigned by PCI-SIG to Intel"  
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  vendor_id = bitstruct.unpack("u16", reg)[0]
  if vendor_id==0x8086:
    return "{0}\t\t{1}".format( bold(green("INTEL")), blue(comment) )
  else:
    return "Unknown\t\t"+blue(comment)   


def decode_SVID_1_30_6_CFG(reg):
  comment="specifies Intel® but can be set to any value once after reset"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  vendor_id = bitstruct.unpack("u16", reg)[0]
  if vendor_id==0x8086:
    return "{0}\t\t{1}".format( bold(green("INTEL")), blue(comment) )
  else:
    return "Unknown\t\t"+blue(comment)   


def decode_PLATFORM_RAPL_LIMIT(reg):
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  lim_lock,_,lim_2_time_x,lim_2_time_y,clmp_lim_2,lim_2_en,lim_2,_,lim_1_time_x,lim_1_time_y,clmp_lim_1,lim_1_en,lim_1 = \
    bitstruct.unpack("b1 u7 u2 u5 b1 b1 u15 u8 u2 u5 b1 b1 u15", reg)
  if lim_lock:
    lock=red("LOCKED")
  else:
    lock=green("UNLOCKED")

  if clmp_lim_2:
    clamp2=green("can go below P1")
  else:
    clamp2=red("is limited between P0 and P1")

  if clmp_lim_1:
    clamp1=green("can go below P1")
  else:
    clamp1=red("is limited between P0 and P1")

  if lim_2_en:
    pl2enable=red("ENABLED")
  else:
    pl2enable=green("DISABLED")

  if lim_1_en:
    pl1enable=red("ENABLED")
  else:
    pl1enable=green("DISABLED")

  time_window2=(1+lim_2_time_x/10)*2**lim_2_time_y
  time_window1=(1+lim_1_time_x/10)*2**lim_1_time_y
  return "{0}\n" \
  "  PKG_PWR_LIM_2_TIME : {1:2.0f} s\t\tTime window over which Power_Limit_2 should be maintained\n" \
  "  PKG_PWR_LIM_2      : {2:3.0f} W ({3})\tPPL2/Package Power Limitation 2, always on\n" \
  "  PBM2               : {4}\n" \
  "  PKG_PWR_LIM_1_TIME : {5:2.1f} ms\t\tThe maximal time window is bounded by PKG_PWR_SKU_MSR[PKG_MAX_WIN]\n" \
  "  PKG_PWR_LIM_1      : {6:3.0f} W ({7})\tPPL1/Package Power Limitation 1\n" \
  "  PBM1               : {8}".format(lock,time_window2*pcu["time_unit"],
                                           lim_2       *pcu["pwr_unit"], pl2enable, clamp2,
                                           time_window1*pcu["time_unit"]*1000,
                                           lim_1       *pcu["pwr_unit"], pl1enable, clamp1)


registers= [
  (0x00, "vendor ID"                , 2, decode_VID_1_30_6_CFG ),
  (0x02, "Device ID"                , 2, "RO 325Ah assigned by each IP/function owner as a unique identifier"),
  (0x04, "PCI Command"              , 2, "mostly hardwired to 0"),
  (0x06, "PCI status"               , 2, ""),
  (0x08, "Rev ID & Class code reg." , 8, ""),
  (0x0C, "CACHE LINE SIZE REGISTER" , 1, "size of cache line"),
  (0x0D, "PCI LATENCY TIMER"        , 1, "Not applicable to PCIe. Hardwired to 0"),
  (0x0E, "HEADER TYPE"              , 1, "PCI header type : multi function device, type 0 header"),
  (0x0F, "BUILT IN SELF TEST"       , 1, "Not supported. Hardwired to 0"),
  (0x2C, "Subsystem vendor ID"      , 2, decode_SVID_1_30_6_CFG),
  (0x2E, "Subsystem ID"             , 2, "Assigned to uniquely identify the subsystem"),
  (0x34, "Capability pointer"       , 1, "Points to the first capability structure : the PCIe capability"),
  (0x3C, "Interrupt line"           , 1, "N/A for PCU"),
  (0x3D, "Interrupt pin"            , 1, "N/A for PCU"),
  (0x3E, "Minimum grant"            , 1, "PCI min grant reg : PCU doesn't burst as a PCI compliant master"),
  (0x3F, "Maximum latency"          , 1, "PCU has no specific requirements for how often it accesses PCI"),
  (0xA8, "PLATFORM RAPL LIMIT"      , 8, decode_PLATFORM_RAPL_LIMIT),
]
