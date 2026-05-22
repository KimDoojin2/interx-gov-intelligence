"""
settings_loader 통합 테스트 — configs/settings.yaml 실제 파일 로드 검증
실행: pytest tests/integration/test_settings.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from interx_engine.infrastructure.config.settings_loader import Settings


class TestSettingsLoad:
    def setup_method(self):
        self.s = Settings()

    def test_project_root_has_configs(self):
        assert (self.s.project_root / "configs").is_dir()

    def test_l3_threshold_is_30(self):
        assert self.s.l3_threshold() == 30

    def test_partner_threshold_is_18(self):
        assert self.s.partner_threshold() == 18

    def test_sim_threshold_in_range(self):
        t = self.s.sim_threshold()
        assert 0.0 < t < 1.0

    def test_top_k_positive(self):
        assert self.s.top_k() >= 1

    def test_urgent_dday_positive(self):
        assert self.s.urgent_dday() >= 1

    def test_retry_total_positive(self):
        assert self.s.retry_total() >= 1

    def test_retry_backoff_positive(self):
        assert self.s.retry_backoff() > 0.0

    def test_retry_status_codes_nonempty(self):
        codes = self.s.retry_status_codes()
        assert isinstance(codes, list)
        assert len(codes) > 0
        assert 500 in codes

    def test_proposal_output_dir_is_path(self):
        d = self.s.proposal_output_dir()
        assert isinstance(d, Path)
        assert "proposal" in str(d).lower()
