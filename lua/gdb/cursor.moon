
line = V.def_tvar("gdb_cursor_line")
sign_id = V.def_tvar("gdb_cursor_sign_id")

fmt = string.format

CursorInit = ->
    line.set(-1)
    sign_id.set(4999)

CursorDisplay = (add) ->
    -- to avoid flicker when removing/adding the sign column(due to the change in
    -- line width), we switch ids for the line sign and only remove the old line
    -- sign after marking the new one
    old_sign_id = sign_id.get()
    sign_id.set(4999 + 4998 - old_sign_id)
    current_buf = V.call("nvimgdb#win#GetCurrentBuffer", {})
    if add != 0 and line.get() != -1 and current_buf != -1
        V.cmd(fmt('sign place %d name=GdbCurrentLine line=%d buffer=%d',
            sign_id.get(), line.get(), current_buf))
    V.cmd('sign unplace ' .. old_sign_id)

ret = {
    init: CursorInit,
    set: line.set,
    display: CursorDisplay,
}

ret