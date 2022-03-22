#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from skywalking.trace.context import get_context

def install():
    from threading import Thread

    ___init__ = Thread.__init__
    Thread.__init__ = _sw___init___func(___init__)

target_arg_idx = 2
target_kwarg_key = 'target'

def _sw___init___func(___init__):
    def _sw___init__(*args, **kwargs):

        target = None
        target_in_arg = False

        # Using kwargs and args to avoid breaking complex arguments used with Thread class' __init__
        if(len(args) > target_arg_idx):
            target_in_arg = True
            target = args[target_arg_idx]
        elif(target_kwarg_key in kwargs):
            target = kwargs[target_kwarg_key]
        
        if(target is not None):

            context = get_context()
            active_span = context.active_span()
            carrier = None
            if(active_span is not None):
                carrier = active_span.inject_async()

            def _sw_target_wrap(*_args, **_kwargs):
                
                context = get_context()
                op = "target"
                if(target.__name__ is not None):
                    op = target.__name__
                
                # We are mostly trying to catch threads that we created ourselves
                # Their target would be called "callback" or "callback_multiple"
                if(op == "_run" or op == "run"):
                    target(*_args, **_kwargs)
                else:
                    with context.new_local_span(op=op, carrier=carrier) as span:
                        target(*_args, **_kwargs)

            if(target_in_arg):
                args[target_arg_idx] = _sw_target_wrap
            else:
                kwargs[target_kwarg_key] = _sw_target_wrap

        return ___init__(*args, **kwargs)

    return _sw___init__
