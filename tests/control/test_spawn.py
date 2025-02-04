# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# February 12 2022, Christian Hopps <chopps@labn.net>
#
# Copyright 2022, LabN Consulting, L.L.C.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; see the file COPYING; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#
"Testing use of pexect/REPL in munet."
import logging
import os
import time

import pytest


# All tests are coroutines
pytestmark = pytest.mark.asyncio


async def _test_repl(unet, hostname, cmd, use_pty, will_echo=False):
    host = unet.hosts[hostname]
    time.sleep(1)
    repl = await host.console(
        cmd, user="root", use_pty=use_pty, will_echo=will_echo, trace=True
    )
    return repl


@pytest.mark.parametrize("host", ["r1", "r2"])
@pytest.mark.parametrize("mode", ["pty", "piped"])
@pytest.mark.parametrize("shellcmd", ["/bin/bash", "/bin/dash", "/usr/bin/ksh"])
async def test_spawn(unet, host, mode, shellcmd):
    if not os.path.exists(shellcmd):
        pytest.skip(f"{shellcmd} not installed skipping")

    os.environ["TEST_SHELL"] = shellcmd
    if mode == "pty":
        repl = await _test_repl(unet, host, [shellcmd], use_pty=True)
    else:
        repl = await _test_repl(unet, host, [shellcmd, "-si"], use_pty=False)

    try:
        rn = unet.hosts[host]
        output = rn.cmd_raises("pwd ; ls -l /")
        logging.debug("pwd and ls -l: %s", output)

        output = repl.cmd_raises("unset HISTFILE LSCOLORS")
        assert not output.strip()

        output = repl.cmd_raises("env | grep TEST_SHELL")
        logging.debug("'env | grep TEST_SHELL' output: %s", output)
        assert output == f"TEST_SHELL={shellcmd}"

        expected = (
            "block\nbus\nclass\ndev\ndevices\nfirmware\nfs\nkernel\nmodule\npower"
        )
        rc, output = repl.cmd_status("ls --color=never -1 /sys")
        output = output.replace("hypervisor\n", "")
        logging.debug("'ls --color=never -1 /sys' rc: %s output: %s", rc, output)
        assert output == expected

        if shellcmd == "/bin/bash":
            output = repl.cmd_raises("!!")
            logging.debug("'!!' output: %s", output)
    finally:
        # this is required for setns() restoration to work for non-pty (piped) bash
        if mode != "pty":
            repl.child.proc.kill()
