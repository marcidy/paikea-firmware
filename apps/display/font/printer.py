import framebuf


def put(fb, text, x, y, font, color):
    adv = 0
    for ch in text:
        gl, gh, gw = font.get_ch(ch)
        gbuf = bytearray(gl)
        if color != 0:
            for i, bval in enumerate(gbuf):
                gbuf[i] = bval ^ 0xFF
        gfb = framebuf.FrameBuffer(gbuf, gw, gh, framebuf.MONO_HLSB)
        fb.blit(gfb, x + adv, y)
        adv += gw
