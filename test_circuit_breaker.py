from common import ConfigLoader, LoggerManager, CircuitBreaker, CircuitBreakerError
from common import UNKNOWN_TEXT
import logging

config: ConfigLoader = ConfigLoader(
    'config/base_config.ini',
    'config/load_compliance_check_config.ini'
)

logger_manager: LoggerManager = LoggerManager(config, script_name='test_circuit_breaker')
logger_manager.configure_application_logger()

logger: logging.Logger = logging.getLogger(__name__)

circuit_breaker: CircuitBreaker = CircuitBreaker(config)

logger.info("Testing circuit breaker with simulated requests")

# Simulate 5 successes
for i in range(5):
    circuit_breaker.before_request()
    circuit_breaker.record_success()
    logger.info(f"Success {i+1} - State: {circuit_breaker.get_state().value}")

# Simulate failures to trip circuit
for i in range(10):
    try:
        circuit_breaker.before_request()
        if i % 2 == 0:
            circuit_breaker.record_failure()
            logger.info(f"Failure {i+1} - State: {circuit_breaker.get_state().value}")
        else:
            circuit_breaker.record_success()
            logger.info(f"Success {i+1} - State: {circuit_breaker.get_state().value}")
    except CircuitBreakerError as e:
        logger.warning(f"Request blocked: {e}")

stats = circuit_breaker.get_statistics()
logger.info(f"Final statistics: {stats}")

print("\n✓ Circuit breaker test complete")
print(f"State: {stats['state']}")
print(f"Total requests: {stats['total_requests']}")
print(f"Failure rate: {stats['failure_rate']}%")