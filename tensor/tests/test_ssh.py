from twisted.trial import unittest

from tensor.sources.linux import basic

testKey = """-----BEGIN RSA PRIVATE KEY-----
Proc-Type: 4,ENCRYPTED
DEK-Info: AES-128-CBC,A6588464A721D661311DBCE44C76337E

/bqr0AEIbiWubFiPEcdlNw8WdDrFqELOCZo78ohtDX/2HJhkMCCtAuv46is5UCvj
pweYupJQgZZ9g+6rKLhTo6d0VYwaSOuR6OJWEecIr7quyQBgCPOvun2fVGrx6/7U
D9HiXBdBDVc4vcEUviZu5V+E9xLmP9GteD1OR7TfR1AqFMPzHVvDE9UxrzEacFY4
KPs7KP6x+8so5KvZSJKisczc+JBt+PlZisDwX9BCHJNmAYYFRm2umY7sCmLNmeoc
Y95E6Tmpze4J1559mLM7nuzOpnnFEii4pA5H7unMUCa9AwkLLYLOV7N8iRETgG0R
snvH5uiVRqEB84ypItCZF+Nk5Y0/WPSWPDq/bhwyQeodEPjlIfiHKzDf9GuuT9El
Q4dGxA0mLOKMqPDJGGc7mwTTN5iczj94gsLTfI1me1qzTzxdko/BMqsmPSUbkNXS
wgkofT+48L00HL9zq0quHkgjoTe1Wud8tI4mG0Tl9BTFE9PUtlfdJNoEQ1dk9RcR
UkhjMbuN3h8r9w9EVugAvbp/c7SQILXEJ6QZK2NMzO01SA5Tv7hmDh1J0lcIF1zb
VI+rlxly/riDN6U9w35vOZEzKl3qYbAXrnRteo7MEYvc/BahvxBP0ZEGRXeoNfAj
JLvBrkhBUVy1cH5fGs2SYIwUEKBx5nLL5NeNI1ymRKbsyJ3oTKZU+PQhfarEJD2r
u/dZoDb/AEjxCkaM1EaDG590Bjc6ZxC1ZkF6gSK27iJRP5CCj5XoD7kIpmZFE+gc
KpVNHHe6ef2ptOngkEDUyTmZ7z18lVCeC4sBPzrLPDnWB+cie+19/cJDJpRz0n0j
qMkh7MY+FQ8t0AopFAy7r50nV5FlGt9rG7YaWO8j5Lv3TsPPDOxFk5IoB6AtRpr8
tSQCCyCcdHkD3M1wI/PD9bEjuELaDG8PaVzOuj5rVyh+saZQeD9GmegsuBkDGb4g
COtzWOQ1H0ii478rbQAxwsOEMdR5lxEFOo8mC0p4mnWJti2DzJQorQC/fjbRRv7z
vfJamXvfEuHj3NPP9cumrskBtD+kRz/c2zgVJ8vwRgNPazdfJqGYjmFB0loVVyuu
x+hBHOD5zyMPFrJW9MNDTiTEaQREaje5tUOfNoA1Wa4s2bVLnhHCXdMSWmiDmJQp
HEYAIZI2OJhMe8V431t6dBx+nutApzParWqET5D0DWvlurDWFrHMnazh164RqsGu
E4Dg6ZsRnI+PEJmroia6gYEscUfd5QSUebxIeLhNzo1Kf5JRBW93NNxhAzn9ZJ9O
2bjvkHOJlADnfON5TsPgroXX95P/9V8DWUT+/ske1Fw43V1pIT+PtraYqrlyvow+
uJMA2q9sRLzXnFb2vg7JdD1XA4f2eUBwzbtq8wSuQexSErWaTx5uAERDnGAWyaN2
3xCYl8CTfF70xN7j39hG/pI0ghRLGVBmCJ5NRzNZ80SPBE/nzYy/X6pGV+vsjPoZ
S3dBmvlBV/HzB4ljsO2pI/VjCJVNZdOWDzy18GQ/jt8/xH8R9Ld6/6tuS0HbiefS
ZefHS5wV1KNZBK+vh08HvX/AY9WBHPH+DEbrpymn/9oAKVmhH+f73ADqVOanMPk0
-----END RSA PRIVATE KEY-----
"""

testKeyPassword = "testtest"

class FakeTensor(object):
    config = {
        'ssh_username': 'test', 
        'ssh_key': testKey,
        'ssh_keypass': testKeyPassword,
    }
    hostConnectorCache = {}

class Tests(unittest.TestCase):
    def _qb(self, result):
        pass

    def test_ssh_source_setup(self):
        s = basic.LoadAverage({
                'interval': 1.0,
                'service': 'mem',
                'ttl': 60,
                'use_ssh': True,
           }, self._qb, FakeTensor())
