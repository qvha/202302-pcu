#!/usr/bin/python3

import os
import sys
import struct
from textwrap import wrap
import bitstruct

from useful_stuff import *

# some command codes for the OS MAILBOX
CONFIG_TDP     = 0x7F
READ_PM_CONFIG = 0x94
WRITE_PM_CONFIG= 0x95
CLOS           = 0xD0

# sub commands for CONFIG_TDP
GET_LEVELS_INFO          = 0x0
GET_CONFIG_TDP_CONTROL   = 0x1
SET_CONFIG_TDP_CONTROL   = 0x2
GET_TDP_INFO             = 0x3
GET_PWR_INFO             = 0x4
GET_TJMAX_INFO           = 0x5
GET_CORE_MASK            = 0x6
GET_TURBO_LIMIT_RATIOS   = 0x7
SET_LEVEL                = 0x8
GET_UNCORE_P0_P1_INFO    = 0x9
GET_P1_INFO              = 0xa
GET_MEM_FREQ             = 0xb
GET_RATIO_INFO           = 0xc
GET_FACT_HP_TURBO_LIMIT_NUMCORES = 0x10
GET_FACT_HP_TURBO_LIMIT_RATIOS = 0x11
GET_FACT_LP_CLIPPING_RATIO = 0x12
PBF_GET_CORE_MASK_INFO   = 0x20
PBF_GETP1HI_P1LO_INFO    = 0x21
PBF_GET_TJ_MAX_INFO      = 0x22
PBF_GET_TDP_INFO         = 0x23
# subcommands for READ_PM_CONFIG
READ_PM_CONFIG_PM_FEATURE = 0x3
# subcommands for WRITE_PM_CONFIG
WRITE_PM_CONFIG_PM_FEATURE= 0x3
# subcommands for CLOS
CLOS_PM_QOS_CONFIG       = 0x2


###################################################################################################
#
#  2. PCU CR1 registers (bus:B31, device:30, function: 1)
#     External Design Specification vol 2 : Registers, §18.2 page 5748
#
###################################################################################################
def decode_VID_1_30_1_CFG(reg):
  comment="assigned by PCI-SIG to Intel"  
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  vendor_id = bitstruct.unpack("u16", reg)[0]
  if vendor_id==0x8086:
    return "{0}\t\t{1}".format( bold(green("INTEL")), blue(comment) )
  else:
    return "Unknown\t\t"+blue(comment)   


def decode_SVID_1_30_1_CFG(reg):
  comment="specifies Intel® but can be set to any value once after reset"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  vendor_id = bitstruct.unpack("u16", reg)[0]
  if vendor_id==0x8086:
    return "{0}\t\t{1}".format( bold(green("INTEL")), blue(comment) )
  else:
    return "Unknown\t\t"+blue(comment)   


def decode_STAT_TEMPTRIP_CFG(reg):
  comment="logs the status of thermtrip and memtrip sources"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,stat_earlydts_cpu_thermtrip,stat_cpu_thermtrip,stat_memtrip1,stat_memtrip0=\
    bitstruct.unpack("u28 b1 b1 b1 b1", reg)
  line0="\t\t"+blue(comment)
  line1="  flags : "
  if stat_earlydts_cpu_thermtrip: line1+=" " + red("STAT_EARLYDTS_CPU_THERMTRIP")
  if stat_cpu_thermtrip:          line1+=" " + red("STAT_CPU_THERMTRIP")
  if stat_memtrip1:               line1+=" " + red("STAT_MEMTRIP1")
  if stat_memtrip0:               line1+=" " + red("STAT_MEMTRIP0")
  return line0+"\n"+line1


def decode_STAT_TEMPHOT_CFG(reg):
  comment="logs the status of memhot and prochot sources"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,stat_memhot1_out,stat_memhot0_out= bitstruct.unpack("u30 b1 b1", reg)
  line0="\t\t"+blue(comment)
  line1="  flags : "
  if stat_memhot1_out: line1+=" " + red("STAT_MEMHOT1_OUT")
  if stat_memhot0_out: line1+=" " + red("STAT_MEMHOT0_OUT")
  return line0+"\n"+line1


def decode_MC_BIOS_REQUEST(reg):
  comment="Memory Controller clock frequency (requested by BIOS)"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,req_type,_,req_data = bitstruct.unpack("u20 u4 u2 u6", reg)
  
  ro=red("RO")
 
  # not exactly the spec. If 0 then, if 1 then, otherwise don't bother
  if   req_type==0: base_freq=133.33
  else            : base_freq=100.00

  return "{0} {1:4.0f}MHz\t{2}\n".format(ro, base_freq*req_data, blue(comment))


def decode_M_COMP_CFG(reg):
  comment="Memory compensation control"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,comp_force,_,comp_interval,comp_disable = bitstruct.unpack("u22 b1 u3 u4 b1", reg)
  
  ro=red("RO")
  
  if comp_disable:
    periodic=ro+" Periodic COMP cycles are "+red("DISABLED")
  else:  
    periodic=ro+" Periodic COMP cycles are "+green("ENABLED")
  line0="{0} {1}\u03BCs\t{2}\n".format(ro, 2**comp_interval*10.24, blue(comment))
  line1="\t\t\t  "+periodic
  return line0+line1


def decode_CSR_DESIRED_CORES_CFG(reg):
  comment="Single bits that were part of CSR_DESIRED_CORES_CFG broken out to this register to "\
          "keep CSR_DESIRED_CORES_CFG to have a core mask only."
  comment=wrap(comment, 65)
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  lock,smt_disable,_,max_cores= bitstruct.unpack("b1 b1 u22 u8", reg)
  if lock: lock=red("LOCKED")
  else:    lock=green("UNLOCKED")

  if smt_disable: ht=yellow("NO_SMT")
  else:           ht=yellow("SMT")
  
  ro=red("RO")

  line0=        "{0} {1}\t{2}\n".format    (ro, lock,      blue(comment[0]) )
  line1="\t\t\t  {0} {1:<5s}\t{2}\n".format(ro, ht,        blue(comment[1]) )
  line2="\t\t\t  {0} {1} cores\t{2}".format(ro, max_cores, blue(comment[2]) )
  return line0+line1+line2


def decode_CSR_DESIRED_CORES_MASK0(reg):
  comment="Number of cores/threads BIOS wants to exist on the next reset. A processor reset "\
          "must be used for this register to take effect. Note, programming this register to a "\
          "value higher than the product has cores should not be done. This register is reset only "\
          "by PWRGOOD."
  wrapped=wrap(comment, 65)
  justified=[ "\t"*5 + s for s in wrapped[1:] ]
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  core_off_mask= bitstruct.unpack("u32", reg)[0]
  
  ro=red("RO")

  line0="{0} {1:08X}\t{2}\n".format(ro, core_off_mask, blue(wrapped[0]) )
  line1="{0}\n".format( blue(justified[0]) )
  line2="{0}\n".format( blue(justified[1]) )
  line3="{0}".format  ( blue(justified[2]) )
  return line0+line1+line2+line3


def decode_SSKPD_CFG(reg):
  comment="This register holds 64 writable bits with no functionality behind them. It is for the "\
          "convenience of BIOS. Address shouldnPLA has hardcoded address for this."
  comment=wrap(comment, 65)
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  d,c,b,a= bitstruct.unpack("u16 u16 u16 u16", reg)
  return "{0} {1}h\t{2}\n\t\t\t\u251C {0} {3}h\t{4}\n\t\t\t\u251C {0} {5}h\t{6}\n\t\t\t\u2514 {0} {7}h".format(
          red("RO"),
          blue("{0:04X}".format(a)), blue(comment[0]),
          blue("{0:04X}".format(b)), blue(comment[1]),
          blue("{0:04X}".format(c)), blue(comment[2]),
          blue("{0:04X}".format(d))
          )


def decode_C2_DDR_TT(reg):
  comment="This register contains the initial DDR timer value. BIOS can update this value during "\
          "run-time. PCODE will sample this register at slow loop. If the value has changed since "\
          "the previous sample and in addition there is no valid Hystereris parameter (HYS) from "\
          "a previous PM_DMD or PM_RSP message, then PCODE will configure DDR_TRANS_TIMER_VALUE "\
          "with this value."
  wrapped=wrap(comment, 65)
  justified=[ "\t"*5 + s for s in wrapped[1:] ]
  comment=[wrapped[0],] + justified
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,ddr_timer_value= bitstruct.unpack("u19 u13", reg)
  return "{0} {1:3d}\t{2}".format(red("RO"), ddr_timer_value,blue("\n".join(comment)))


def decode_C2C3TT_CFG(reg):
  comment="This register contains the initial snoop timer (pop-down) value. "\
          "BIOS can update this value during run-time. " \
          "PCODE will sample this register at slow loop. If the value has changed since the "\
          "previous sample and in addition there is no valid Hystereris parameter (HYS) from a "\
          "previous PM_DMD or PM_RSP message, then PCODE will configure "\
          "IMPH_CR_SNP_RELOAD[LIM] with this value."
  wrapped=wrap(comment, 65)
  justified=[ "\t"*5 + s for s in wrapped[1:] ]
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  comment=[wrapped[0],] + justified
  _,ppdn_init= bitstruct.unpack("u20 u12", reg)
  return "{0} {1:3d}\t{2}".format(red("RO"), ppdn_init,blue("\n".join(comment)))


def decode_TSOD_CONTROL_CFG(reg):
  comment="Polling interval for TSOD (Thermal Sensor On Dimm), set by BIOS"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  _,tsod_polling_interval= bitstruct.unpack("u27 u5", reg)
  return "{0} {1}s\t{2}".format(red("RO"), tsod_polling_interval/8,blue(comment))


def decode_PCIe_ILTR_OVERRIDE_CFG(reg):
  comment="Override parameters for received LTR messages from PCI Express"
  reg=bitstruct.byteswap("{}".format(len(reg)),reg)
  sxl_v,force_sxl,_,sxlm,sxl,nl_v,force_nl,_,multiplier,nstl= \
          bitstruct.unpack("b1 b1 b1 u3 u10 b1 b1 b1 u3 u10", reg)

  if not sxl_v:
    result="\n  \u251C {0} {1} the snoop latency override value".format(green("RW"), bold("Ignore")) 
  else:  
    if force_sxl: forced=bold("(forced)")
    else:         forced=""
    if sxlm==0 and sxl==0:
      result="\n  \u251C {1} Latency requirement for snoop requests : {0} the best possible service is requested".format(yellow("UNSET"), green("RW")) 
    else:
      result="\n  \u251C {1} Latency requirement for snoop requests : {0} ={2}ns {3}".format(
            yellow("SET"), 
            green("RW"),
            yellow(sxlm*sxl),
            forced
            )

  if not nl_v:
    result+="\n  \u2514 {0} {1} the non-snoop latency override value".format(green("RW"),bold("Ignore"))
  else:
    if force_nl: forced=bold("(forced)")
    else:         forced=""
    if multiplier==0 and nstl==0:
      result+="\n  \u2514 {1} Latency requirement for non_snoop requests : {0} the best possible service is requested".format(yellow("UNSET"), green("RW")) 
    else:
      result+="\n  \u2514 {1} Latency requirement for non_snoop requests : {0} ={2}ns {3}".format(
            yellow("SET"), 
            green("RW"),
            yellow(multiplier*nstl),
            forced
            )
  return "\t\t{}".format(blue(comment))+result


registers= [
  (0x00, "vendor ID"                , 2, decode_VID_1_30_1_CFG ),
  (0x02, "Device ID"                , 2, "RO 3259h assigned by each IP/function owner as a unique identifier"),
  (0x04, "PCI Command"              , 2, "mostly hardwired to 0"),
  (0x06, "PCI status"               , 2, ""),
  (0x08, "Rev ID & Class code reg." , 8, ""),
  (0x0C, "CACHE LINE SIZE REGISTER" , 1, "size of cache line"),
  (0x0D, "PCI LATENCY TIMER"        , 1, "Not applicable to PCIe. Hardwired to 0"),
 (0x0E, "HEADER TYPE"              , 1, "PCI header type : multi function device, type 0 header"),
  (0x0F, "BUILT IN SELF TEST"       , 1, "Not supported. Hardwired to 0"),
  (0x2C, "Subsystem vendor ID"      , 2, decode_SVID_1_30_1_CFG),
  (0x2E, "Subsystem ID"             , 2, "Assigned to uniquely identify the subsystem"),
  (0x34, "Capability pointer"       , 1, "Points to the first capability structure : the PCIe capability"),
  (0x3C, "Interrupt line"           , 1, "N/A for PCU"),
  (0x3D, "Interrupt pin"            , 1, "N/A for PCU"),
  (0x3E, "Minimum grant"            , 1, "PCI min grant reg : PCU doesn't burst as a PCI compliant master"),
  (0x3F, "Maximum latency"          , 1, "PCU has no specific requirements for how often it accesses PCI"),
  (0x80, "TEMPTRIP STATUS"          , 4, decode_STAT_TEMPTRIP_CFG),
  (0x84, "TEMPHOT STATUS"           , 4, decode_STAT_TEMPHOT_CFG),
  (0x8C, "BIOS MAILBOX DATA"        , 4, ""),
  (0x90, "BIOS MAILBOX INTERFACE"   , 4, ""),
  (0x94, "BIOS RESET CPL CFG"       , 4, ""),
  (0x98, "MC BIOS REQUEST"          , 4, decode_MC_BIOS_REQUEST),
  (0xA0, "OS MAILBOX DATA"          , 4, ""),
  (0xA4, "OS MAILBOX INTERFACE"     , 4, ""),
  (0xB8, "MEMORY COMP CONTROL"      , 4, decode_M_COMP_CFG),
  (0xBC, "CSR DESIRED CORES CFG"    , 4, decode_CSR_DESIRED_CORES_CFG),
  (0xC0, "CSR DESIRED CORES MASK0"  , 4, decode_CSR_DESIRED_CORES_MASK0),
  (0xC4, "CSR DESIRED CORES MASK1"  , 4, ""),
  (0xC8, "CSR DESIRED CORES MASK2"  , 4, ""),
  (0xCC, "CSR DESIRED CORES MASK3"  , 4, ""),
  (0xD0, "SSKPD CFG"                , 8, decode_SSKPD_CFG),
  (0xD8, "C2 DDR TT"                , 4, decode_C2_DDR_TT),
  (0xDC, "C2C3TT CFG"               , 4, decode_C2C3TT_CFG),
  (0xE0, "TSOD CONTROL"             , 4, decode_TSOD_CONTROL_CFG),
  (0xFC, "PCIe ILTR OVERRIDE CFG"   , 4, decode_PCIe_ILTR_OVERRIDE_CFG),
]
