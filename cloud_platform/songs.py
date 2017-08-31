# -*- coding: utf-8 -*-


def install_exoscale(ctx):
    ctx.env['cloud.platform'].install_exoscale()


def install_ovh(ctx):
    ctx.env['cloud.platform'].install_ovh()
