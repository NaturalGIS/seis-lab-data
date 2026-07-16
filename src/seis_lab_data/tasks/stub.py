import dramatiq
from dramatiq.brokers.stub import StubBroker

# this _stub_broker is only meant as a way to be able to register actors
# without triggering the unwanted side-effect of having dramatiq eagerly
# trying to connect to it
sld_stub_broker = StubBroker()
dramatiq.set_broker(sld_stub_broker)
