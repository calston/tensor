"""Tensor - A monitoring client for Riemann

.. moduleauthor:: Colin Alston <colin@imcol.in>

"""

from tensor import service

def makeService(config):
    # Create TensorService
    return service.TensorService(config)

