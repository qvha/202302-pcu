#!/usr/bin/python3

import time
import textwrap

###################################################################################################
#
#  0. Some useful routines for later
#
###################################################################################################

debug = False


def bold(text):
  return '\033[1m'+text+'\033[0m'

def red(text):
  return '\033[31m'+text+'\033[0m'

def blue(text):
  return '\033[34m'+text+'\033[0m'

def yellow(text):
  return '\033[33m'+text+'\033[0m'

def green(text):
  return '\033[32m'+text+'\033[0m'

def magenta(text):
  return '\033[35m'+text+'\033[0m'

def cyan(text):
  return '\033[36m'+text+'\033[0m'

def lightgrey(text):
  return '\033[37m'+text+'\033[0m'

def darkgrey(text):
  return '\033[90m'+text+'\033[0m'

def highlight(text):
  return '\033[43;30m'+text+'\033[0m'


pcu={ "energy_unit": 0,
      "time_unit": 0,
      "pwr_unit": 0
    }

def format_array( data ):
  """
     formats an array for display on console.
     data: array of tuples, each tuple is a "line", ( "variable name", "value with unit", "commentary" )
  """
  result=[]
  ndata=len(data)
  for idata,mytuple in enumerate(data):
    sname,svalue,commentary=mytuple
    wrapped = textwrap.wrap(commentary, width=80)
    n = len(wrapped)     # number of lines in the paragraph
    # first line
    if n<2:
      # ... and last line of data  
      if idata==ndata-1:
        result.append( " \u2514 {0:30s}: {1:6s} {2}".format( sname, svalue, blue(wrapped[0]) ) )            
      else:  
        result.append( " \u251C {0:30s}: {1:6s} {2}".format( sname, svalue, blue(wrapped[0]) ) )            
      continue
    else:  
      result.append( " \u251C {0:30s}: {1:6s} {2}".format( sname, svalue, blue(wrapped[0]) ) )            

    # following lines
    for i in range(1,n-1):
      result.append( " \u2502"+" "*40 + blue(wrapped[i]) )  
    # last line of paragraph  
    if idata==ndata-1:
      # ... and last line of data  
      result.append( " \u2514"+" "*40 + blue(wrapped[n-1]) )  
    else:  
      result.append( " \u2502"+" "*40 + blue(wrapped[n-1]) )  

  return "\n".join(result)
