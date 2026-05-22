"""
WinPredictionUseCase — 수주 가능성 스코어링 v2
피처: 기본 6개 + v3 고도화 6개 = 최대 12개
모델: 룰 기반 → sklearn LR → GradientBoosting 앙상블 (자동 선택)

모드 1 (기본): 룰 기반 가중합
모드 2 (ML):   WinPredictionTrainer로 학습한 sklearn 모델 로드 시 자동 사용
"""
from __future__ import annotations

import json
import logging
import pickle
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.core.entities.prediction_result import PredictionResult, WinPredictionReport
from interx_engine.infrastructure.utils.budget_parser import normalize_budget

log = logging.getLogger("interx.win_prediction")

# ── sklearn 모델 경로 ─────────────────────────────────────────────────────────
_MODEL_FILENAME = "win_pred_model.pkl"   # v2: 앙상블 모델


def _model_path() -> Path:
    """data/models/win_pred_model.pkl 경로 반환."""
    try:
        from interx_engine.infrastructure.config.settings_loader import settings
        return Path(settings.project_root) / "data" / "models" / _MODEL_FILENAME
    except Exception:
        return Path.cwd() / "data" / "models" / _MODEL_FILENAME


def _legacy_model_path() -> Path:
    """v1 호환: win_pred_lr.pkl 경로."""
    p = _model_path()
    return p.parent / "win_pred_lr.pkl"


def _load_sklearn_model() -> Optional[dict]:
    """
    저장된 sklearn 모델 번들 로드.
    v2 모델 우선, 없으면 v1(LR) 모델 fallback.
    번들 구조: {"model": clf, "scaler": StandardScaler, "feature_names": [...], "accuracy": float}
    """
    for path in [_model_path(), _legacy_model_path()]:
        if not path.exists():
            continue
        try:
            with open(path, "rb") as f:
                bundle = pickle.load(f)
            log.info("[WinPred] sklearn 모델 로드: %s (accuracy=%.3f, model=%s)",
                     path.name, bundle.get("accuracy", 0.0),
                     type(bundle.get("model")).__name__)
            return bundle
        except Exception as exc:
            log.warning("[WinPred] sklearn 모델 로드 실패 (%s) → 다음 시도", exc)
    return None


# ── 피처 가중치 v2 (합계 = 1.0) ──────────────────────────────────────────────
_WEIGHTS_V2 = {
    # 기본 피처 (0.70)
    "fitness_score":   0.25,
    "priority_score":  0.18,
    "budget_score":    0.10,   # v2: normalized budget (0~1)
    "dday_urgency":    0.08,
    "l3_flag":         0.09,
    # v3 고도화 피처 (0.30)
    "tfidf_similarity": 0.08,  # InterX 프로필 유사도
    "keyword_density":  0.06,  # 키워드 밀도
    "type_multiplier":  0.05,  # 공고 유형 배율
    "combo_count":      0.06,  # 콤보 키워드 히트 수
    "industry_score":   0.05,  # 솔루션 적합도
}

_GRADE_THRESHOLDS = [
    (0.75, "A", "즉시투자"),
    (0.55, "B", "검토"),
    (0.35, "C", "관망"),
    (0.00, "D", "제외"),
]


def _budget_score(raw: str) -> float:
    """예산 → 0~1 스코어 (10억 기준 정규화, 너무 크면 역효과)"""
    try:
        norm = normalize_budget(raw) or ""
        digits = "".join(c for c in norm if c.isdigit() or c == ".")
        억 = float(digits) if digits else 0.0
        if 억 <= 0:
            return 0.0
        if 억 <= 10:
            return 억 / 10.0
        return max(0.3, 1.0 - (억 - 10) / 100)   # 과도하게 크면 경쟁 심해 감점
    except Exception:
        return 0.0


def _dday_score(deadline: str) -> float:
    """마감일 → 0~1 (30일 이내면 긴급 가산, 너무 멀면 0.3 베이스)"""
    try:
        delta = (date.fromisoformat(deadline[:10]) - date.today()).days
        if delta < 0:
            return 0.0
        if delta <= 7:
            return 1.0
        if delta <= 30:
            return 0.7
        return 0.3
    except Exception:
        return 0.3


def _grade(prob: float):
    for threshold, grade, action in _GRADE_THRESHOLDS:
        if prob >= threshold:
            return grade, action
    return "D", "제외"


def _extract_v2_features(notice: Notice, sc: ScoreCard) -> Dict[str, float]:
    """Notice + ScoreCard → v2 피처 딕셔너리 (12개)."""
    return {
        "fitness_score":   min(sc.fitness_score / 100.0, 1.0),
        "priority_score":  min(sc.priority_score / 100.0, 1.0),
        "budget_score":    _budget_score(notice.budget),
        "dday_urgency":    _dday_score(notice.deadline_date),
        "l3_flag":         1.0 if notice.l3_strong == "Y" else 0.0,
        "industry_score":  min(sc.industry_score / 100.0, 1.0),
        # v3 고도화 피처
        "tfidf_similarity": sc.tfidf_similarity,
        "keyword_density":  min(sc.keyword_density, 1.0),
        "type_multiplier":  sc.type_multiplier,
        "combo_count":      min(len(sc.combo_keywords) / 10.0, 1.0),
        "budget_grade":     min(sc.budget_score / 10.0, 1.0),
        "urgency_boost":    min(sc.urgency_boost / 25.0, 1.0),
    }


# ── v1 호환 피처 이름 ────────────────────────────────────────────────────────
_FEATURE_NAMES_V1 = [
    "fitness_score", "priority_score", "budget_억",
    "dday_urgency", "l3_flag", "industry_score",
]

_FEATURE_NAMES_V2 = [
    "fitness_score", "priority_score", "budget_score", "dday_urgency",
    "l3_flag", "industry_score",
    "tfidf_similarity", "keyword_density", "type_multiplier",
    "combo_count", "budget_grade", "urgency_boost",
]


class WinPredictionUseCase:
    """
    공고별 수주 가능성을 0~1 확률과 A/B/C/D 등급으로 반환한다.

    - data/models/win_pred_model.pkl 이 존재하면 앙상블 모델 사용
    - win_pred_lr.pkl 존재하면 LR 모델 사용
    - 없으면 룰 기반 가중합 (_WEIGHTS_V2) 사용
    - WinPredictionTrainer.train() 으로 모델 학습 가능
    """

    def __init__(self):
        self._sklearn_bundle = _load_sklearn_model()

    @property
    def model_info(self) -> Dict[str, str]:
        """현재 로드된 모델 정보."""
        if self._sklearn_bundle is None:
            return {"mode": "rule_v2", "model": "WeightedSum", "accuracy": "-"}
        b = self._sklearn_bundle
        return {
            "mode": "ml",
            "model": type(b["model"]).__name__,
            "accuracy": f'{b.get("accuracy", 0):.1%}',
            "n_samples": str(b.get("n_samples", "?")),
            "features": str(len(b.get("feature_names", []))),
        }

    def _sklearn_prob(self, features: dict) -> Optional[float]:
        """sklearn 모델로 수주 확률 계산. 실패 시 None 반환."""
        if self._sklearn_bundle is None:
            return None
        try:
            import numpy as np
            bundle  = self._sklearn_bundle
            model   = bundle["model"]
            scaler  = bundle["scaler"]
            f_names = bundle["feature_names"]
            x = np.array([[features.get(k, 0.0) for k in f_names]])
            x_scaled = scaler.transform(x)
            prob = float(model.predict_proba(x_scaled)[0][1])
            return round(prob, 3)
        except Exception as exc:
            log.debug("[WinPred] sklearn 예측 실패: %s → 룰 기반 fallback", exc)
            return None

    def execute(
        self,
        notices: List[Notice],
        score_cards: List[ScoreCard],
        execution_id: str = "",
    ) -> WinPredictionReport:
        sc_map = {s.notice_id: s for s in score_cards}
        report = WinPredictionReport(
            execution_id=execution_id,
            model_version="ml_v2" if self._sklearn_bundle else "rule_v2",
        )

        for notice in notices:
            sc = sc_map.get(notice.notice_id)
            if not sc:
                continue

            # ── v2 피처 계산 ─────────────────────────────────────────────────
            features = _extract_v2_features(notice, sc)

            # sklearn 모델 우선, 없으면 룰 기반
            sklearn_prob = self._sklearn_prob(features)
            if sklearn_prob is not None:
                prob = sklearn_prob
            else:
                # v2 룰 기반 가중합
                prob = sum(
                    _WEIGHTS_V2.get(k, 0) * v
                    for k, v in features.items()
                    if k in _WEIGHTS_V2
                )

            grade, action = _grade(prob)

            contributions = {
                k: round(_WEIGHTS_V2.get(k, 0) * v, 3)
                for k, v in features.items()
                if k in _WEIGHTS_V2
            }

            report.predictions.append(PredictionResult(
                notice_id=notice.notice_id,
                site=notice.site,
                title=notice.title[:60],
                win_probability=round(prob, 3),
                win_grade=grade,
                feature_contributions=contributions,
                recommended_priority=action,
            ))

        # 상위 기회 식별 (A등급, 확률 상위 5개)
        report.predictions.sort(key=lambda x: -x.win_probability)
        report.top_opportunities = [
            p.notice_id for p in report.predictions if p.win_grade == "A"
        ][:5]

        a_cnt = sum(1 for p in report.predictions if p.win_grade == "A")
        log.info("[WinPred] 예측 완료: 총 %d건 | A등급 %d건 | 모드=%s",
                 len(report.predictions), a_cnt, report.model_version)
        return report


# ═══════════════════════════════════════════════════════════════════════════════
# 자동 JSONL 학습 데이터 내보내기
# ═══════════════════════════════════════════════════════════════════════════════

def export_training_data(
    notices: List[Notice],
    score_cards: List[ScoreCard],
    execution_id: str = "",
) -> Optional[Path]:
    """파이프라인 실행 결과를 JSONL 형식으로 data/exports/training/에 저장."""
    try:
        from interx_engine.infrastructure.config.settings_loader import settings
        root = Path(settings.project_root)
    except Exception:
        root = Path.cwd()

    out_dir = root / "data" / "exports" / "training"
    out_dir.mkdir(parents=True, exist_ok=True)

    sc_map = {s.notice_id: s for s in score_cards}
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"train_{timestamp}.jsonl"

    records = []
    for notice in notices:
        sc = sc_map.get(notice.notice_id)
        if not sc:
            continue
        features = _extract_v2_features(notice, sc)
        rec = {
            "notice_id": notice.notice_id,
            "site": notice.site,
            "title": notice.title[:80],
            "grade": sc.priority_grade,
            "execution_id": execution_id,
            "timestamp": timestamp,
            # 기본 피처 (v1 호환)
            "fitness_score": sc.fitness_score,
            "priority_score": sc.priority_score,
            "budget": notice.budget or "",
            "deadline_date": notice.deadline_date or "",
            "l3_strong": notice.l3_strong,
            "industry_score": sc.industry_score,
            # v2 확장 피처
            "tfidf_similarity": sc.tfidf_similarity,
            "keyword_density": sc.keyword_density,
            "type_multiplier": sc.type_multiplier,
            "combo_count": len(sc.combo_keywords),
            "budget_score_v2": sc.budget_score,
            "urgency_boost": sc.urgency_boost,
            "notice_type": sc.notice_type,
            # 정규화된 피처 벡터
            **{f"f_{k}": v for k, v in features.items()},
        }
        records.append(rec)

    if not records:
        return None

    out_file.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records),
        encoding="utf-8",
    )
    log.info("[WinPred] 학습 데이터 저장: %s (%d건)", out_file.name, len(records))
    return out_file


# ═══════════════════════════════════════════════════════════════════════════════
# WinPredictionTrainer — 앙상블 모델 학습기 v2
# ═══════════════════════════════════════════════════════════════════════════════


class WinPredictionTrainer:
    """
    SQLite DB + CRM 메모(crm_memos.json) + JSONL 학습 데이터에서
    GradientBoosting / RandomForest / LogisticRegression 앙상블 학습.

    레이블 결정 우선순위:
      1순위: crm_memos.json 에 status == "수주" → 1 / "탈락" → 0
      2순위: priority_grade (A/B → 1, C/D → 0) 로 대체

    최소 20건 미만이면 학습 불가 (ValueError 발생).

    사용법
    ------
    trainer = WinPredictionTrainer()
    result  = trainer.train()   # {"accuracy": 0.82, "n_samples": 120, ...}
    """

    def __init__(self, db_path: str = "", memos_path: str = ""):
        try:
            from interx_engine.infrastructure.config.settings_loader import settings
            root = Path(settings.project_root)
        except Exception:
            root = Path.cwd()

        self.db_path    = Path(db_path)    if db_path    else root / "data" / "interx_pipeline.db"
        self.memos_path = Path(memos_path) if memos_path else root / "data" / "crm_memos.json"
        self.model_out  = _model_path()

    # ── 피처 추출 (v2 확장) ───────────────────────────────────────────────────

    @staticmethod
    def _extract_features(row: dict) -> Optional[List[float]]:
        """DB 행(dict) → v2 피처 벡터. 필수값 누락 시 None."""
        try:
            f_fitness   = min(float(row.get("fitness_score",   0) or 0) / 100.0, 1.0)
            f_priority  = min(float(row.get("priority_score",  0) or 0) / 100.0, 1.0)
            f_budget    = _budget_score(str(row.get("budget", "") or ""))
            f_dday      = _dday_score(str(row.get("deadline_date", "") or ""))
            f_l3        = 1.0 if str(row.get("l3_strong", "N")) == "Y" else 0.0
            f_industry  = min(float(row.get("industry_score", 0) or 0) / 100.0, 1.0)
            # v2 확장 피처
            f_tfidf     = float(row.get("f_tfidf_similarity", row.get("tfidf_similarity", 0)) or 0)
            f_density   = min(float(row.get("f_keyword_density", row.get("keyword_density", 0)) or 0), 1.0)
            f_type_mult = float(row.get("f_type_multiplier", row.get("type_multiplier", 1.0)) or 1.0)
            f_combo     = min(float(row.get("f_combo_count", row.get("combo_count", 0)) or 0) / 10.0, 1.0)
            f_budg_grade = min(float(row.get("f_budget_grade", row.get("budget_score_v2", 0)) or 0) / 10.0, 1.0)
            f_urgency   = min(float(row.get("f_urgency_boost", row.get("urgency_boost", 0)) or 0) / 25.0, 1.0)
            return [f_fitness, f_priority, f_budget, f_dday, f_l3, f_industry,
                    f_tfidf, f_density, f_type_mult, f_combo, f_budg_grade, f_urgency]
        except Exception:
            return None

    # ── 데이터 로드 ───────────────────────────────────────────────────────────

    def _load_data(self) -> Tuple[List[List[float]], List[int]]:
        """
        (X, y) 반환. y: 1=win, 0=loss
        데이터 소스 우선순위:
          1) crm_memos.json (수주/탈락 실 레이블)
          2) data/exports/training/*.jsonl (파이프라인 자동 저장)
          3) SQLite DB notices 테이블 (priority_grade 대리 레이블)
        """
        import sqlite3

        # ── CRM 메모 true 레이블 ──────────────────────────────────────────────
        true_labels: dict = {}
        if self.memos_path.exists():
            try:
                memos = json.loads(self.memos_path.read_text(encoding="utf-8"))
                for notice_id, memo in memos.items():
                    st = memo.get("status", "")
                    if st == "수주":
                        true_labels[notice_id] = 1
                    elif st == "탈락":
                        true_labels[notice_id] = 0
            except Exception as exc:
                log.warning("[Trainer] crm_memos 로드 실패: %s", exc)

        X, y = [], []
        label_source = {"crm": 0, "jsonl": 0, "db": 0, "skipped": 0}
        seen_ids: set = set()

        # ── JSONL 파일에서 데이터 로드 ────────────────────────────────────────
        jsonl_dir = self.db_path.parent / "exports" / "training"
        if jsonl_dir.exists():
            for jf in sorted(jsonl_dir.glob("*.jsonl"), reverse=True):
                try:
                    for line in jf.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        rec = json.loads(line)
                        nid = str(rec.get("notice_id", ""))
                        if nid in seen_ids:
                            continue
                        feats = self._extract_features(rec)
                        if feats is None:
                            label_source["skipped"] += 1
                            continue
                        if nid in true_labels:
                            X.append(feats); y.append(true_labels[nid])
                            label_source["crm"] += 1
                        else:
                            if "win_label" in rec:
                                lbl = int(rec["win_label"])
                            else:
                                grade_str = str(rec.get("grade", ""))
                                if grade_str in ("A", "B"):
                                    lbl = 1
                                elif grade_str in ("C", "D"):
                                    lbl = 0
                                else:
                                    label_source["skipped"] += 1
                                    continue
                            X.append(feats); y.append(lbl)
                            label_source["jsonl"] += 1
                        seen_ids.add(nid)
                except Exception as exc:
                    log.warning("[Trainer] JSONL 로드 실패 %s: %s", jf.name, exc)

        # ── SQLite DB 보완 ────────────────────────────────────────────────────
        if self.db_path.exists():
            try:
                with sqlite3.connect(str(self.db_path)) as con:
                    con.row_factory = sqlite3.Row
                    existing = {r[1] for r in con.execute(
                        "PRAGMA table_info(notices)").fetchall()}

                    def _col(name, default="0"):
                        return name if name in existing else f"{default} AS {name}"

                    sel = ", ".join([
                        "notice_id",
                        _col("fitness_score"),
                        _col("priority_score"),
                        _col("budget", "''"),
                        _col("deadline_date", "''"),
                        _col("l3_strong", "''"),
                        _col("industry_score"),
                        _col("priority_grade", "''"),
                    ])
                    rows = con.execute(f"SELECT {sel} FROM notices").fetchall()

                for row in rows:
                    row_dict = dict(row)
                    nid = str(row_dict.get("notice_id", ""))
                    if nid in seen_ids:
                        continue
                    grade_str = str(row_dict.get("priority_grade", ""))
                    if grade_str not in ("A", "B", "C", "D"):
                        label_source["skipped"] += 1
                        continue
                    feats = self._extract_features(row_dict)
                    if feats is None:
                        label_source["skipped"] += 1
                        continue
                    lbl = 1 if grade_str in ("A", "B") else 0
                    if nid in true_labels:
                        lbl = true_labels[nid]
                        label_source["crm"] += 1
                    else:
                        label_source["db"] += 1
                    X.append(feats); y.append(lbl)
                    seen_ids.add(nid)
            except Exception as exc:
                log.warning("[Trainer] SQLite 로드 실패: %s", exc)

        log.info("[Trainer] 데이터 로드: 총 %d건 (CRM=%d, JSONL=%d, DB=%d, 스킵=%d)",
                 len(X), label_source["crm"], label_source["jsonl"],
                 label_source["db"], label_source["skipped"])
        return X, y

    # ── 학습 ─────────────────────────────────────────────────────────────────

    def train(self, min_samples: int = 20, model_type: str = "auto") -> dict:
        """
        모델 학습 후 data/models/win_pred_model.pkl 저장.

        model_type:
          "auto"    — 50건 이상이면 GBM, 아니면 LR
          "gbm"     — GradientBoosting 강제
          "rf"      — RandomForest 강제
          "lr"      — LogisticRegression 강제
          "ensemble"— 3모델 VotingClassifier

        Returns: {"accuracy": float, "cv_mean": float, "n_samples": int, ...}
        """
        import numpy as np
        from sklearn.linear_model import LogisticRegression
        from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
        from sklearn.model_selection import cross_val_score, train_test_split
        from sklearn.preprocessing import StandardScaler

        X_raw, y_raw = self._load_data()

        if len(X_raw) < min_samples:
            raise ValueError(
                f"학습 데이터 부족: {len(X_raw)}건 (최소 {min_samples}건 필요). "
                "파이프라인을 더 실행하거나 CRM 메모(수주/탈락)를 입력하세요."
            )

        X = np.array(X_raw, dtype=float)
        y = np.array(y_raw, dtype=int)

        # 클래스 불균형 확인
        n_win  = int(y.sum())
        n_loss = len(y) - n_win
        log.info("[Trainer] 클래스 분포: win=%d, loss=%d", n_win, n_loss)

        if n_win == 0:
            raise ValueError("win(A/B) 데이터가 0건입니다. 파이프라인 실행 후 재시도하세요.")
        if n_win < 5:
            log.warning("[Trainer] win 샘플 %d건 — 더 많은 A/B 공고 수집 시 정확도 향상됩니다.", n_win)

        # 모델 선택
        if model_type == "auto":
            model_type = "gbm" if len(X) >= 50 else "lr"

        # 스케일링
        scaler   = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # 교차 검증
        cv_folds = max(2, min(5, n_win))

        if model_type == "gbm":
            model = GradientBoostingClassifier(
                n_estimators=100, max_depth=3, learning_rate=0.1,
                min_samples_split=5, min_samples_leaf=2,
                random_state=42, subsample=0.8,
            )
            model_name = "GradientBoosting"
        elif model_type == "rf":
            model = RandomForestClassifier(
                n_estimators=100, max_depth=5,
                min_samples_split=5, min_samples_leaf=2,
                class_weight="balanced", random_state=42,
            )
            model_name = "RandomForest"
        elif model_type == "ensemble":
            from sklearn.ensemble import VotingClassifier
            lr = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
            gbm = GradientBoostingClassifier(
                n_estimators=80, max_depth=3, learning_rate=0.1, random_state=42)
            rf = RandomForestClassifier(
                n_estimators=80, max_depth=5, class_weight="balanced", random_state=42)
            model = VotingClassifier(
                estimators=[("lr", lr), ("gbm", gbm), ("rf", rf)],
                voting="soft",
            )
            model_name = "VotingEnsemble"
        else:  # lr
            model = LogisticRegression(
                class_weight="balanced", max_iter=1000, random_state=42, C=1.0,
            )
            model_name = "LogisticRegression"

        try:
            cv_scores = cross_val_score(model, X_scaled, y, cv=cv_folds, scoring="roc_auc")
            cv_mean   = float(cv_scores.mean())
            log.info("[Trainer] CV ROC-AUC: %.3f ± %.3f (%d-fold, %s)",
                     cv_mean, cv_scores.std(), cv_folds, model_name)
        except Exception as e:
            log.warning("[Trainer] CV 실패 (%s) → 학습 계속 진행", e)
            cv_mean = 0.0

        # 전체 데이터로 최종 학습
        model.fit(X_scaled, y)

        # 피처 중요도 (GBM/RF만 지원)
        feature_importance = {}
        if hasattr(model, "feature_importances_"):
            for i, fname in enumerate(_FEATURE_NAMES_V2):
                feature_importance[fname] = round(float(model.feature_importances_[i]), 4)
        elif hasattr(model, "coef_"):
            for i, fname in enumerate(_FEATURE_NAMES_V2):
                feature_importance[fname] = round(abs(float(model.coef_[0][i])), 4)

        # 홀드아웃 정확도
        if len(X) >= 30 and n_win >= 2:
            try:
                Xtr, Xte, ytr, yte = train_test_split(
                    X_scaled, y, test_size=0.3, random_state=42,
                    stratify=y if n_win >= 2 else None
                )
                model_eval = type(model)(**model.get_params()) if not model_type == "ensemble" else model
                if model_type != "ensemble":
                    model_eval.fit(Xtr, ytr)
                    accuracy = float(model_eval.score(Xte, yte))
                else:
                    accuracy = cv_mean if cv_mean > 0 else 0.5
            except Exception:
                accuracy = cv_mean if cv_mean > 0 else 0.5
        else:
            accuracy = cv_mean if cv_mean > 0 else 0.5

        # 저장
        bundle = {
            "model":              model,
            "scaler":             scaler,
            "feature_names":      _FEATURE_NAMES_V2,
            "accuracy":           accuracy,
            "cv_roc_auc":         cv_mean,
            "n_samples":          len(X),
            "n_win":              n_win,
            "model_type":         model_name,
            "feature_importance": feature_importance,
            "trained_at":         datetime.now().isoformat(),
        }
        self.model_out.parent.mkdir(parents=True, exist_ok=True)
        with open(self.model_out, "wb") as f:
            pickle.dump(bundle, f)

        log.info("[Trainer] 모델 저장: %s (accuracy=%.3f, model=%s)",
                 self.model_out, accuracy, model_name)
        return {
            "accuracy":           round(accuracy, 3),
            "cv_roc_auc":         round(cv_mean, 3),
            "n_samples":          len(X),
            "n_win":              n_win,
            "n_loss":             n_loss,
            "model_type":         model_name,
            "model_path":         str(self.model_out),
            "feature_importance": feature_importance,
        }
