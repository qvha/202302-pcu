#!/usr/bin/python3

import os
import sys
import tty
import time
import struct
import termios
from textwrap import wrap
import argparse
import bitstruct
import threading
import subprocess
import multiprocessing

from useful_stuff import *
import PCU_CR0
import PCU_CR1
import PCU_CR2
import PCU_CR3
import PCU_CR4
import PCU_CR6

# number of CR "Champ de Registres"
# it's 8 on SPR, and 7 on cascadelake. init() will find out and change this value
nCR=8

def keyreader(sndkey_pipe):
  key_mapping = {
        127: 'backspace',
        10: 'return',
        32: 'space',
        9: 'tab',
        27: 'esc',
        65: 'up',
        66: 'down',
        67: 'right',
        68: 'left'
  }
  old_settings = termios.tcgetattr(sys.stdin)
  tty.setcbreak(sys.stdin.fileno())

  while True:
    b = os.read(sys.stdin.fileno(), 3).decode()
    if len(b) == 3:
      k = ord(b[2])
    else:
      k = ord(b)
    if k==27 or k==113:
      sndkey_pipe.send("esc")
      break
    # general case
    sndkey_pipe.send( key_mapping.get(k, chr(k) ) )  # sends a unicode string

  termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


###################################################################################################
#
#  9. a place holder for Work In Progress
#
###################################################################################################
wip=[
 (0x00, "───────────────────────────────────────", 8, ""),
 (0x00, "───▐▀▄───────▄▀▌───▄▄▄▄▄▄▄─────────────", 8, ""),
 (0x00, "───▌▒▒▀▄▄▄▄▄▀▒▒▐▄▀▀▒██▒██▒▀▀▄──────────", 8, ""),
 (0x00, "──▐▒▒▒▒▀▒▀▒▀▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▀▄────────", 8, ""),
 (0x00, "──▌▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▄▒▒▒▒▒▒▒▒▒▒▒▒▀▄──────", 8, ""),
 (0x00, "▀█▒▒▒█▌▒▒█▒▒▐█▒▒▒▀▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▌─────", 8, ""),
 (0x00, "▀▌▒▒▒▒▒▒▀▒▀▒▒▒▒▒▒▀▀▒▒▒▒▒▒▒▒▒▒▒▒▒▒▐───▄▄", 8, ""),
 (0x00, "▐▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▌▄█▒█", 8, ""),
 (0x00, "▐▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒█▒█▀─", 8, ""),
 (0x00, "▐▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒█▀───", 8, ""),
 (0x00, "▐▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▌────", 8, ""),
 (0x00, "─▌▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▐─────", 8, ""),
 (0x00, "─▐▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▌─────", 8, ""),
 (0x00, "──▌▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▐──────", 8, ""),
 (0x00, "──▐▄▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▄▌──────", 8, ""),
 (0x00, "────▀▄▄▀▀▀▀▀▄▄▀▀▀▀▀▀▀▄▄▀▀▀▀▀▄▄▀────────", 8, "")
 ]


###################################################################################################
#
#  3. main routine that deals with displaying things on the terminal
#     uses "config" (256 bytes) of binary registers to decode,
#     and "registers" a constant array that describes the bitfield
#
###################################################################################################
def update_display(config, registers):
  for offset,text,size, comment in registers:
    reg = bytearray(config[offset:offset+size])
  
    if size==0:
      print( "{0:24s}".format( text ) )
    elif size==1:
      hexa = "{0:02X}".format( reg[0] )
      print( u"{0:24s}: {1}h\t\t{2}".format( text, blue(hexa), blue(comment) ) )
    elif size==2:
      if not isinstance(comment, str):
        print( u"{0:24s}: {1}".format( text, comment(reg) ) )
      else:  
        a,b = struct.unpack("<BB", reg)
        hexa = "{1:02X}{0:02X}".format( a, b )
        print( "{0:24s}: {1}h\t\t{2}".format( text, blue(hexa), blue(comment) ) )
    elif size==4:
      if not isinstance(comment, str):
        print( "{0:24s}: {1}".format( text, comment(reg) ) )
      else:
        a,b,c,d = struct.unpack("<BBBB", reg)
        hexa = "{3:02X}{2:02X}{1:02X}{0:02X}".format( a,b,c,d )
        print( "{0:24s}: {1}h\t{2}".format( text, blue(hexa), blue(comment) ) )
    elif size==8:
      if not isinstance(comment, str):
        print( "{0:24s}: {1}".format( text, comment(reg) ) )
      else:  
        a,b,c,d,e,f,g,h = struct.unpack("<BBBBBBBB", reg)
        hexa = "{7:02X}{6:02X}{5:02X}{4:02X}{3:02X}{2:02X}{1:02X}{0:02X}".format( a,b,c,d,e,f,g,h )
        print( "{0:24s}: {1}h\t{2}".format( text, blue(hexa), blue(comment) ) )
    else:
      print( "{0:24s}{1}".format( text, comment(reg) ) )
  
  
###################################################################################################
#
#  1. The orchestrator is the backend. launches threads and processus as necessary
#     the GUI interface is the frontend.
#     Both are launched from main()
#     if some data must not be garbage collected, it should be passed as a argument to main()
#
###################################################################################################
def orchestrator( args, PCUTable ):
  global debug
  global nCR

  rcvkey_pipe,sndkey_pipe = multiprocessing.Pipe(False)

  nPCU=len(PCUTable)
  if debug : print("orchestrator: nCR={0} nPCU={1}".format(nCR,nPCU))

  # a pair of communication pipes, for each readers. one reader per RC field (8)
  rcvcmd_pipe=[]
  sndcmd_pipe=[]
  # for each reader_slave, I.E. for each RC ...
  for i in range(nCR):
    rcvcmd_p,sndcmd_p = multiprocessing.Pipe(False)
    rcvcmd_pipe.append(rcvcmd_p)
    sndcmd_pipe.append(sndcmd_p)
    #preload the pipe with the first PCU/CPU
    sndcmd_p.send(PCUTable[0])

  bar1 = multiprocessing.Barrier(nCR+1)

  config     = multiprocessing.RawArray('B', 256*nCR )        # unsigned chars (1 byte each)
  new_config = multiprocessing.RawArray('B', 256*nCR )        # unsigned chars (1 byte each)

  p=[ multiprocessing.Process( target=reader_slave,
                               args  =(i, new_config, bar1, rcvcmd_pipe[i]) )
      for i in range(nCR)
    ]
  for i in range(nCR): p[i].start()


  # keyboard management in a separate process, because it mostly waits on input
  pkr = threading.Thread( target=keyreader, args=(sndkey_pipe,) )
  pkr.start()

  CRTable=[ PCU_CR0.registers,  PCU_CR1.registers, PCU_CR2.registers, PCU_CR3.registers,
            PCU_CR4.registers, wip, PCU_CR6.registers, wip]
  CRindex =0  # up to nCR-1
  PCUindex=0  # up to nCPU-1
  while True:
    time.sleep(.08)  # 12Hz
    bar1.wait()
    # while slaves are writing to new_config ...

    # process keyboard input, if there are any
    if rcvkey_pipe.poll():
      k=rcvkey_pipe.recv()
      #print("{}".format(k))
      #time.sleep(3)
      
      # access Register field RC  #k ; shouldn't be more than 0-7
      if k in "0123456789":
        kk=int(k)
        if kk>=nCR: continue    # ignore out of range requests
        else: CRindex=kk
      elif k=="right":
        PCUindex=(PCUindex+1)%nPCU
        # for all eight RC reader_slaves, update the file/CPU to read  
        [ sndcmd_pipe[i].send(PCUTable[PCUindex]) for i in range(nCR) ]  
      elif k=="left":
        PCUindex=(PCUindex-1)%nPCU
        # for all eight RC reader_slaves, update the file/CPU to read  
        [ sndcmd_pipe[i].send(PCUTable[PCUindex]) for i in range(nCR) ]  
      elif k=="a":
        sndcmd_pipe[CRindex].send("HACK1")  
      elif k=="b":
        sndcmd_pipe[CRindex].send("HACK2")  
      elif k=="esc":
        break  

      else:
        print("Could not decode "+k)

    CPUheader=[ "[CPU{}]".format(i) for i in range(1,nPCU+1) ]
    CPUheader[PCUindex]=highlight(CPUheader[PCUindex])
    CRheader=["[CR0]", "[CR1]", "[CR2]", "[CR3]", "[CR4]", "[CR5]", "[CR6]", "[CR7]"][:nCR]
    if debug: print("orchestrator: CRindex={0} CRheader={1}".format(CRindex, CRheader))
    CRheader[CRindex]=highlight(CRheader[CRindex])
    #move cursor to upper left corner
    print( '\033[0;37;40m;\033[1;1f\033[2J'+"Dumping registers for :", " ".join(CPUheader))
    print( "PCU registers :", " ".join(CRheader))
    update_display(config[256*CRindex:256*(CRindex+1)], CRTable[CRindex]) 
    for i in range(nCR): config[256*i:256*(i+1)]=new_config[256*i:256*(i+1)]

  # loop was exited
  [ sndcmd_pipe[i].send("ESC") for i in range(nCR) ]  
  bar1.abort()
  [ p[i].join()                for i in range(nCR) ]  
  pkr.join()
  return


# one reader per RC ; i is the RC number. (1-8) rcvcmd_pipe will bring the file name to
# open, which is related the the CPU we will be reading on (2-32)
def reader_slave(i, config, barrier, rcvcmd_pipe):
  fd=None  
  while True:
    try:  
      barrier.wait()
    except:
      break  
        
    # process the command channel first
    if rcvcmd_pipe.poll():
      cmd=rcvcmd_pipe.recv()
      if cmd=="ESC":
        break  
      elif cmd=="HACK1":
        """
        command,subcommand =rcvcmd_pipe.recv()
        mailbox_data,mailbox_interface=format_mail(0, command, subcommand)
        fd.seek(0xA4)   # offset to MAILBOX_INTERFACE
        # fd.write(mailbox_data)
        fd.write(mailbox_interface)
        """

        # HACK : writing PACKAGE RAPL LIMIT CFG to increase PL1 and PL2 TDP, and time windows
        if i == 0:               # if the user is watching RC0
          fd.seek(0xE8)          # go to RAPL LIMIT CFG
          reg=fd.read(8)
          reg=bitstruct.byteswap("{}".format(len(reg)),reg)
          lim_lock,_,lim_2_time_x,lim_2_time_y,clmp_lim_2,lim_2_en,lim_2,_,lim_1_time_x,lim_1_time_y,clmp_lim_1,lim_1_en,lim_1 = \
          bitstruct.unpack("b1 u7 u2 u5 b1 b1 u15 u8 u2 u5 b1 b1 u15", reg)
          if not lim_lock:
            # local constants
            lim_lock=False  # When set, all settings in this register are locked and are treated as Read Only.
            lim_1_en=True   # Because the cpu must maintain the power consumption to TDP, lim_1_en is always True
            lim_2_en=True   # The Package PL2 is always enabled. Writing a 0 to the bit will have no effect.
            clmp_lim_1=True # This bit is writable only when CPUID.(EAX=6):EAX[4] is set
            clmp_lim_2=True # This bit is writable only when CPUID.(EAX=6):EAX[4] is set

            lim_1=500*8
            lim_2=764*8
            lim_2_time_x=3
            lim_1_time_x=3
            lim_1_time_y=31
            lim_2_time_y=31

            swapped=bitstruct.pack("b1 p7 u2 u5 b1 b1 u15 p8 u2 u5 b1 b1 u15",
                   lim_lock,lim_2_time_x,lim_2_time_y,clmp_lim_2,lim_2_en,lim_2,lim_1_time_x,lim_1_time_y,clmp_lim_1,lim_1_en,lim_1 )
            wr_chunk=bitstruct.byteswap("{}".format(len(swapped)),swapped)
            fd.seek(0xE8)
            fd.write(wr_chunk)

        # HACK : writing PLATFORM RAPL LIMIT, to maximize Plateform TDP and time window
        # PLATEFORM is core + GT + uncore
        elif i == 6:
        # if the user is watching RC6
          fd.seek(0xA8) 
          # go to PLATEFORM RAPL LIMIT CFG
          reg=fd.read(8)
          reg=bitstruct.byteswap("{}".format(len(reg)),reg)
          lim_lock,_,lim_2_time_x,lim_2_time_y,clmp_lim_2,lim_2_en,lim_2,_,lim_1_time_x,lim_1_time_y,clmp_lim_1,lim_1_en,lim_1 = \
          bitstruct.unpack("b1 u7 u2 u5 b1 b1 u15 u8 u2 u5 b1 b1 u15", reg)
          if not lim_lock:
            # local constants
            lim_lock=False  # When set, all settings in this register are locked and are treated as Read Only.
            lim_1_en=True   # Because the cpu must maintain the power consumption to TDP, lim_1_en is always True
            lim_2_en=True   # The Package PL2 is always enabled. Writing a 0 to the bit will have no effect.
            clmp_lim_1=True # This bit is writable only when CPUID.(EAX=6):EAX[4] is set
            clmp_lim_2=True # This bit is writable only when CPUID.(EAX=6):EAX[4] is set

            lim_1=32767
            lim_2=32767
            lim_2_time_x=3
            lim_1_time_x=3
            lim_1_time_y=31
            lim_2_time_y=31

            swapped=bitstruct.pack("b1 p7 u2 u5 b1 b1 u15 p8 u2 u5 b1 b1 u15",
                   lim_lock,lim_2_time_x,lim_2_time_y,clmp_lim_2,lim_2_en,lim_2,lim_1_time_x,lim_1_time_y,clmp_lim_1,lim_1_en,lim_1 )
            wr_chunk=bitstruct.byteswap("{}".format(len(swapped)),swapped)
            fd.seek(0xA8)
            fd.write(wr_chunk)

        # HACK : writing CONFIG TDP NOMINAL[TDP_RATIO]
        elif i == 3:       # if the user is watching RC3
          fd.seek(0xDC)    # go to CONFIG TDP NOMINAL
          swapped=bitstruct.pack("u8", 40)
          wr_chunk=bitstruct.byteswap("{}".format(len(swapped)),swapped)
          fd.write(wr_chunk)

      elif cmd=="HACK2":
        if i==0:          # if the user is watching RC0

          # HACK : increase CURRENT LIMIT from 550A to 700A. inactive, didn't work  
          fd.seek(0xF8)   # go to VR CURRENT CONFIG CFG
          psi3_threshold=0
          psi2_threshold=0
          psi1_threshold=0
          lock=False
          current_limit=700 * 8     # in units of .125A
          swapped=bitstruct.pack("p2 u10 u10 u10 b1 p18 u13",
                                 psi3_threshold,
                                 psi2_threshold,
                                 psi1_threshold,
                                 lock,
                                 current_limit)
          wr_chunk=bitstruct.byteswap("{}".format(len(swapped)),swapped)
          fd.write(wr_chunk)

          # HACK : modify Pmax control bits
          fd.seek(0xC0)   # go to VR CURRENT CONFIG CFG
          swapped=bitstruct.pack("p29 b1 b1 b1", True, False, False)
          wr_chunk=bitstruct.byteswap("{}".format(len(swapped)),swapped)
          fd.write(wr_chunk)

      else:
        # it's a PCI bus device name
        if fd is not None: fd.close()
        # example : fd=open("/sys/bus/pci/devices/0001:3f:1e.{}/config".format(i),"rb")
        fd=open("/sys/bus/pci/devices/{0}.{1}/config".format(cmd, i),"w+b", buffering=0)

    # allowing for some un predicted misshaps
    if fd is not None:
      fd.seek(0)
      config[256*i:256*(i+1)]= fd.read(256)

  # the loop was escaped  
  if fd is not None: fd.close()
  if debug: print("reader #{} has exited".format(i) )
  return


def init():
  # process cntl+C
  # signal.signal(signal.SIGINT, signal_handler)

  parser = argparse.ArgumentParser(description="Dumps PCU (Power Control Unit) registers, For Each PCUs. Written for Sapphire Rapids & Cascade Lake.",
           epilog="(c) 2023 HA Quoc Viet" )

  parser.add_argument("--debug",  "-g", action="store_true", default=False)
  #parser.add_argument("--device", "-d",                      default="0000:7f:1e",
  #         help="Device to read. Defaults to first module, first socket. "\
  #         "Use \"lspci -n | grep 3258\" to find yours. "
  #         "Example : --device 0000:ff:1e" )
  
  # discover where the PCUs are
  # dirty version using lspci. don't blame me, I have 10min before a meeting
  PCUTable=[]
  commande=[ "lspci", "-Ds", "1e.0" ] 
  p=subprocess.Popen( commande, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, universal_newlines=True )
  # typical output, here on 8S :
  #0000:3f:1e.0 System peripheral: Intel Corporation Device 3258 (rev 06)
  #0000:7f:1e.0 System peripheral: Intel Corporation Device 3258 (rev 06)
  #0000:bf:1e.0 System peripheral: Intel Corporation Device 3258 (rev 06)
  #0000:ff:1e.0 System peripheral: Intel Corporation Device 3258 (rev 06)
  #0001:3f:1e.0 System peripheral: Intel Corporation Device 3258 (rev 06)
  #0001:7f:1e.0 System peripheral: Intel Corporation Device 3258 (rev 06)
  #0001:bf:1e.0 System peripheral: Intel Corporation Device 3258 (rev 06)
  #0001:ff:1e.0 System peripheral: Intel Corporation Device 3258 (rev 06)
  # BUT, true 2S EMR replies
  # 7f:1e.0 0880: 8086:3258 (rev 02)
  # ff:1e.0 0880: 8086:3258 (rev 02)
  # option "-D" solves this
  for dataline in p.stdout:
    if dataline.strip("\n ") == "": continue
    PCUTable.append( dataline.split()[0][:-2] )  # cutting ".0" out

  # [ "0000:3f:1e", "0000:7f:1e", .... ]
  # full path will be like :  /sys/devices/pci0000:ff/0000:ff:1e.2
  # or equivalent             /sys/bus/pci/devices/0000:7f:1e.2

  # checking whether RC7 exists or not . SPR has it; CascadeLake doesn't
  global nCR

  nCR=0
  # debug=True
  # if debug : print("init: PCUTable={}".format(PCUTable))
  for i in range(8):
    pathname="/sys/bus/pci/devices/"+PCUTable[0]+".{}".format(i)
    # if debug : print("init: testing "+pathname)
    if os.path.isdir(pathname):
      nCR+=1
  
  # trap for strange unforseen pathnames
  if nCR==0:
      print("fatal error : could not find any register for the PCU devices at {}.\n"
            "Check code and system at /sys/bus/pci/devices/\nExiting.".format(PCUTable))  
      sys.exit(1)

  return parser.parse_args(),PCUTable


###################################################################################################
#
#  2. main function. "init", then works
#
###################################################################################################
def main():
  global debug

  args,PCUTable=init()
  debug = args.debug

  # backbone program: holds the global logic, launches the genomic threads, blocks on input, sets
  # flags appropriately for the GUI
  orchestrator(args, PCUTable)


if __name__ == '__main__':
  main()
