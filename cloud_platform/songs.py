
def install_exoscale(ctx):
    ctx.env['cloud.platform'].install('exoscale')


def install_ovh(ctx):
    ctx.env['cloud.platform'].install('ovh')
