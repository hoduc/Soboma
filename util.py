from enum import IntEnum


class DebugPrintLevel(IntEnum):
    DEBUG = 1
    INFO = 2
    WARN = 3
    ERROR = 4

current_debug_print_level = DebugPrintLevel.INFO
current_debug_print = True

def dbg_print(msg, debug_print_level, should_print = True):
    if should_print:
        print("{} {}".format("[" + debug_print_level + "]", msg))

def dbgp_helper(msg, debug_log_level):
    should_print = current_debug_print and (int(current_debug_print_level) <= int(debug_log_level))
    dbg_print(msg, debug_log_level.name, should_print)

def dbgp(msg):
    dbgp_helper(msg, DebugPrintLevel.DEBUG)

def dbgpi(msg):
    dbgp_helper(msg, DebugPrintLevel.INFO)

def dbgpw(msg):
    dbgp_helper(msg, DebugPrintLevel.WARN)

def dbgpe(msg):
    dbgp_helper(msg, DebugPrintLevel.ERROR)
