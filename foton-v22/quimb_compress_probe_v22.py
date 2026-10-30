#!/usr/bin/env python3
import inspect
import quimb.tensor as qtn
for n in sorted(dir(qtn)):
    if 'compress' in n.lower() or 'mps' in n.lower() and 'tensor_network' in n.lower():
        obj=getattr(qtn,n)
        try: sig=str(inspect.signature(obj)) if callable(obj) else ''
        except: sig='?'
        print(n,sig)
