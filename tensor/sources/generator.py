"""
.. module:: generator
   :platform: Any
   :synopsis: A function generator source module

.. moduleauthor:: Colin Alston <colin@imcol.in>
"""

import time, math

from twisted.internet import defer, reactor

from zope.interface import implements

from tensor.interfaces import ITensorSource
from tensor.objects import Source

class Function(Source):
    """Produces an arbitrary function

    Functions can contain the functions sin, cos, sinh, cosh, tan, tanh, asin,
    acos, atan, asinh, acosh, atanh, log(n, [base|e]), abs

    Or the constants e, pi, and variable x

    **Configuration arguments:**
    
    :param dx: Resolution with time (steps of x)
    :type dx: float.
    :param function: Function to produce
    :type function: string.
    """

    implements(ITensorSource)

    x = 0

    def get(self):
        self.x += self.config.get('dx', 0.1)

        val = eval(self.config.get('function', 'sin(x)'), {
            'sin': math.sin,
            'sinh': math.sinh,
            'cos': math.cos,
            'cosh': math.cosh,
            'tan': math.tan,
            'tanh': math.tanh,
            'asin': math.asin,
            'acos': math.acos,
            'atan': math.atan,
            'asinh': math.asinh,
            'acosh': math.acosh,
            'atanh': math.atanh,
            'log': math.log,
            'abs': abs,
            'e': math.e,
            'pi': math.pi,
            'x': self.x
        })

        return self.createEvent('ok', 'Sine wave', val)
