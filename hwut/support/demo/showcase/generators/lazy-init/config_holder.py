"""config_holder.py -- lazily created configuration object, shared by the
request threads of a service: double-checked locking, cut into atomic steps.
A call of get_config is a generator: every 'next()' performs ONE step and
yields its name.

    get_publish_early   assigns the shared reference, THEN fills the object
                        -- what a C/C++/Java compiler or CPU may do with
                        'instance = new Config()' when the reference is not
                        published with a barrier (no volatile / atomic)
    get_publish_late    builds and fills a local object, publishes it last
"""


class Config:
    def __init__(self):
        self.port = None                 # filled by load


class Holder:
    def __init__(self):
        self.instance = None
        self.lock_by  = None
        self.built    = 0
        self.seen     = []               # (who, port the caller read)


def _get(holder, who, early):
    inst = holder.instance;                      yield "chk1 " + ("set" if inst else "none")
    if inst is None:
        while holder.lock_by is not None:        yield "wait"
        holder.lock_by = who;                    yield "lock"
        if holder.instance is None:
            yield "chk2 none"
            if early:
                holder.instance = Config(); holder.built += 1;  yield "publish"
                holder.instance.port = 8080;                    yield "fill"
            else:
                c = Config(); c.port = 8080; holder.built += 1; yield "build"
                holder.instance = c;                            yield "publish"
        else:
            yield "chk2 set"
        holder.lock_by = None;                   yield "unlock"
        inst = holder.instance
    holder.seen.append((who, inst.port));        yield "use %s" % inst.port


def get_publish_early(holder, who):
    return _get(holder, who, early=True)


def get_publish_late(holder, who):
    return _get(holder, who, early=False)
