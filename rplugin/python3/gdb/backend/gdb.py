"""GDB specifics."""

import logging
import os
import re
from typing import Dict, List
from gdb.backend import parser_impl
from gdb.backend import base


class _ParserImpl(parser_impl.ParserImpl):
    def __init__(self, common, handler):
        super().__init__(common, handler)

        re_prompt = re.compile(r'\x1a\x1a\x1a$')
        re_jump = re.compile(r'[\r\n]\x1a\x1a([^:]+):(\d+):\d+')
        self.add_trans(self.paused,
                       re.compile(r'[\r\n]Continuing\.'),
                       self._paused_continue)
        self.add_trans(self.paused, re_jump, self._paused_jump)
        self.add_trans(self.paused, re_prompt, self._query_b)
        self.add_trans(self.running,
                       re.compile(r'[\r\n]Breakpoint \d+'),
                       self._query_b)
        self.add_trans(self.running, re_prompt, self._query_b)
        self.add_trans(self.running, re_jump, self._paused_jump)

        self.state = self.running


class _BreakpointImpl(base.BaseBreakpoint):
    def __init__(self, proxy):
        """ctor."""
        self.proxy = proxy
        self.logger = logging.getLogger("Gdb.Breakpoint")

    def _resolve_file(self, fname):
        """Resolve filename full path into its debugger presentation."""
        resp = self.proxy.query(f"handle-command info source {fname}")
        self.logger.debug(resp)
        pattern = re.compile(r"Current source file is ([^\r\n]+)")
        match = pattern.search(resp)
        if match:
            self.logger.info(match.group(1))
            return match.group(1)
        return fname

    def query(self, fname: str):
        self.logger.info("Query breakpoints for %s", fname)
        fname_sym = self._resolve_file(fname)
        if fname != fname_sym:
            self.logger.info("Map file path %s to %s", fname, fname_sym)
        response = self.proxy.query("handle-command info breakpoints")
        if not response:
            return {}

        return self._parse_response(response, fname_sym)

    def _parse_response(self, response: str, fname_sym: str):
        # Select lines in the current file with enabled breakpoints.
        pos_pattern = re.compile(r"([^:]+):(\d+)")
        enb_pattern = re.compile(r"\sy\s+0x")
        breaks: Dict[str, List[str]] = {}
        for line in response.splitlines():
            try:
                if enb_pattern.search(line):    # Is enabled?
                    fields = re.split(r"\s+", line)
                    # file.cpp:line
                    match = pos_pattern.fullmatch(fields[-1])
                    if not match:
                        continue
                    is_end_match = fname_sym.endswith(match.group(1))
                    is_end_match_full_path = fname_sym.endswith(
                        os.path.realpath(match.group(1)))
                    if (match and
                            (is_end_match or is_end_match_full_path)):
                        line = match.group(2)
                        # If a breakpoint has multiple locations, GDB only
                        # allows to disable by the breakpoint number, not
                        # location number.  For instance, 1.4 -> 1
                        br_id = fields[0].split('.')[0]
                        try:
                            breaks[line].append(br_id)
                        except KeyError:
                            breaks[line] = [br_id]
            except IndexError:
                continue
            except ValueError:
                self.logger.exception('Exception')

        return breaks


class Gdb(base.BaseBackend):
    """GDB parser and FSM."""

    def create_parser_impl(self, common, handler):
        """Create parser implementation instance."""
        return _ParserImpl(common, handler)

    def create_breakpoint_impl(self, proxy):
        """Create breakpoint implementation instance."""
        return _BreakpointImpl(proxy)

    command_map = {
        'delete_breakpoints': 'delete',
        'breakpoint': 'break',
    }

    def translate_command(self, command):
        """Adapt command if necessary."""
        return self.command_map.get(command, command)
