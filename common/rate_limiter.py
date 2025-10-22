from __future__ import annotations
import logging
import time
from typing import Optional, List
from datetime import datetime, timedelta
from enum import Enum

logger: logging.Logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit tripped, refusing requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open"""
    pass


class CircuitBreaker:
    """
    Circuit breaker for API rate limiting and failure handling
    
    Monitors API request success/failure rate and opens circuit when
    failure rate exceeds threshold, preventing additional load on struggling server.
    """
    
    def __init__(self, config: 'ConfigLoader') -> None:
        """
        Initialise circuit breaker
        
        Args:
            config: ConfigLoader instance
        """
        self.config: 'ConfigLoader' = config
        
        self.failure_threshold: float = config.getfloat('circuit_breaker', 'failure_threshold_percent') / 100
        self.recovery_threshold: float = config.getfloat('circuit_breaker', 'recovery_threshold_percent') / 100
        self.open_duration: int = config.getint('circuit_breaker', 'circuit_open_duration_seconds')
        self.sample_size: int = config.getint('circuit_breaker', 'sample_size')
        
        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.success_count: int = 0
        self.last_failure_time: Optional[datetime] = None
        self.opened_at: Optional[datetime] = None
        
        self.recent_requests: List[bool] = []
        
        logger.info(f"Circuit breaker initialised: failure_threshold={self.failure_threshold*100}%, "
                   f"recovery_threshold={self.recovery_threshold*100}%, "
                   f"open_duration={self.open_duration}s, sample_size={self.sample_size}")
    
    def _calculate_failure_rate(self) -> float:
        """Calculate failure rate from recent requests"""
        if not self.recent_requests:
            return 0.0
        
        failures: int = sum(1 for success in self.recent_requests if not success)
        return failures / len(self.recent_requests)
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt circuit reset"""
        if self.opened_at is None:
            return False
        
        time_open: timedelta = datetime.now() - self.opened_at
        return time_open.total_seconds() >= self.open_duration
    
    def before_request(self) -> None:
        """
        Call before making API request
        
        Raises:
            CircuitBreakerError if circuit is open
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker entering HALF_OPEN state (testing recovery)")
            else:
                time_remaining: float = self.open_duration - (datetime.now() - self.opened_at).total_seconds()
                raise CircuitBreakerError(
                    f"Circuit breaker is OPEN. Server is struggling. "
                    f"Retry in {time_remaining:.0f} seconds."
                )
    
    def record_success(self) -> None:
        """Record successful API request"""
        self.success_count += 1
        self.recent_requests.append(True)
        
        if len(self.recent_requests) > self.sample_size:
            self.recent_requests.pop(0)
        
        if self.state == CircuitState.HALF_OPEN:
            failure_rate: float = self._calculate_failure_rate()
            if failure_rate <= self.recovery_threshold:
                self.state = CircuitState.CLOSED
                self.opened_at = None
                logger.info(f"Circuit breaker CLOSED (recovered). Failure rate: {failure_rate*100:.1f}%")
        
        if self.state == CircuitState.CLOSED:
            logger.debug(f"Request successful. Failure rate: {self._calculate_failure_rate()*100:.1f}%")
    
    def record_failure(self) -> None:
        """Record failed API request"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        self.recent_requests.append(False)
        
        if len(self.recent_requests) > self.sample_size:
            self.recent_requests.pop(0)
        
        failure_rate: float = self._calculate_failure_rate()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.opened_at = datetime.now()
            logger.warning(f"Circuit breaker reopened OPEN (recovery failed). "
                          f"Failure rate: {failure_rate*100:.1f}%")
        
        elif self.state == CircuitState.CLOSED:
            if len(self.recent_requests) >= self.sample_size and failure_rate > self.failure_threshold:
                self.state = CircuitState.OPEN
                self.opened_at = datetime.now()
                logger.warning(f"Circuit breaker OPEN (failure threshold exceeded). "
                              f"Failure rate: {failure_rate*100:.1f}%. "
                              f"Pausing requests for {self.open_duration}s")
            else:
                logger.debug(f"Request failed. Failure rate: {failure_rate*100:.1f}%")
    
    def get_state(self) -> CircuitState:
        """Get current circuit state"""
        return self.state
    
    def get_statistics(self) -> dict[str, any]:
        """Get circuit breaker statistics"""
        failure_rate: float = self._calculate_failure_rate()
        
        return {
            'state': self.state.value,
            'total_requests': self.success_count + self.failure_count,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'failure_rate': round(failure_rate * 100, 2),
            'recent_sample_size': len(self.recent_requests),
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'last_failure': self.last_failure_time.isoformat() if self.last_failure_time else None
        }
    
    def reset(self) -> None:
        """Reset circuit breaker to initial state"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.opened_at = None
        self.recent_requests = []
        logger.info("Circuit breaker reset to CLOSED state")


if __name__ == "__main__":
    from .config import ConfigLoader
    from .logger import LoggerManager
    
    try:
        config: ConfigLoader = ConfigLoader(
            '../config/base_config.ini',
            '../config/load_compliance_check_config.ini'
        )
        
        logger_manager: LoggerManager = LoggerManager(config, script_name='test_circuit_breaker')
        logger_manager.configure_application_logger()
        
        circuit_breaker: CircuitBreaker = CircuitBreaker(config)
        
        print("\n=== Testing Circuit Breaker ===\n")
        
        print("1. Simulating successful requests (should stay CLOSED):")
        for i in range(5):
            circuit_breaker.before_request()
            circuit_breaker.record_success()
            print(f"   Request {i+1}: SUCCESS - State: {circuit_breaker.get_state().value}")
        
        print(f"\n2. Simulating failures (should trip to OPEN at 50% failure rate):")
        for i in range(10):
            try:
                circuit_breaker.before_request()
                if i % 2 == 0:
                    circuit_breaker.record_failure()
                    print(f"   Request {i+1}: FAILED - State: {circuit_breaker.get_state().value}")
                else:
                    circuit_breaker.record_success()
                    print(f"   Request {i+1}: SUCCESS - State: {circuit_breaker.get_state().value}")
            except CircuitBreakerError as e:
                print(f"   Request {i+1}: BLOCKED - {e}")
        
        print(f"\n3. Waiting for circuit to enter HALF_OPEN...")
        print(f"   (would normally wait {circuit_breaker.open_duration}s)")
        circuit_breaker.opened_at = datetime.now() - timedelta(seconds=circuit_breaker.open_duration + 1)
        
        print(f"\n4. Testing recovery (should close on success):")
        try:
            circuit_breaker.before_request()
            circuit_breaker.record_success()
            print(f"   Recovery request: SUCCESS - State: {circuit_breaker.get_state().value}")
        except CircuitBreakerError as e:
            print(f"   Recovery blocked: {e}")
        
        print(f"\n5. Statistics:")
        stats: dict = circuit_breaker.get_statistics()
        for key, value in stats.items():
            print(f"   {key}: {value}")
        
        print("\n✓ Circuit breaker test complete")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()