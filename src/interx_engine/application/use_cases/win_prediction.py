"""
WinPredictionUseCase — 수주 가능성 스코어링
피처: fitness_score, priority_score, budget_억, dday_urgency, l3_flag, industry_score

모드 1 (기본): 룰 기반 가중합
모드 2 (ML):   WinPredictionTrainer로 학습한 sklearn 모델 로드 시 자동 사용
"""
from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import List, Optional, Tuple

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.core.entities.prediction_result import PredictionResult, WinPredictionReport
from interx_engine.infrastructure.utils.budget_parser import normalize_budget

log = logging.getLogger("interx.win_prediction")

# ── sklearn 모델 경로 ─────────────────────────────────────────────────────────
_MODEL_FILENAME = "win_pred_lr.pkl"


def _model_path() -> Path:
    """data/models/win_pred_lr.pkl 경로 반환."""
    try:
        from interx_engine.infrastructure.config.settings_loader import settings
        return Path(settings.project_root) / "data" / "models" / _MODEL_FILENAME
    except Exception:
        return Path.cwd() / "data" / "models" / _MODEL_FILENAME


def _load_sklearn_model() -> Optional[dict]:
    """
    저장된 sklearn 모델 번들 로드.
    번들 구조: {"model": LR, "scaler": StandardScaler, "feature_names": [...], "accuracy": float}
    """
    path = _model_path()
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            bundle = pickle.load(f)
        log.info("[WinPred] sklearn 모델 로드: %s (accuracy=%.3f)",
                 path, bundle.get("accuracy", 0.0))
        return bundle
    except Exception as exc:
        log.warning("[WinPred] sklearn 모델 로드 실패 (%s) → 룰 기반 사용", exc)
        return None

# ── 피처 가중치 (합계 = 1.0) ──────────────────────────────────────────────────
_WEIGHTS = {
    "fitness_score":   0.35,
    "priority_score":  0.25,
    "budget_억":       0.15,   # 예산 클수록 경쟁 치열, 비선형
    "dday_urgency":    0.10,   # 마감 임박일수록 높음
    "l3_flag":         0.10,
    "industry_score":  0.05,
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
        from datetime import date
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


class WinPredictionUseCase:
    """
    공고별 수주 가능성을 0~1 확률과 A/B/C/D 등급으로 반환한다.

    - data/models/win_pred_lr.pkl 이 존재하면 sklearn LR 모델 사용
    - 없으면 룰 기반 가중합 (_WEIGHTS) 사용
    - WinPredictionTrainer.train() 으로 모델 학습 가능
    """

    def __init__(self):
        self._sklearn_bundle = _load_sklearn_model()

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
            x = np.array([[features[k] for k in f_names]])
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
        report = WinPredictionReport(execution_id=execution_id)

        for notice in notices:
            sc = sc_map.get(notice.notice_id)
            if not sc:
                continue

            # ── 피처 계산 ────────────────────────────────────────────────────
            f_fitness   = min(sc.fitness_score / 100.0, 1.0)
            f_priority  = min(sc.priority_score / 100.0, 1.0)
            f_budget    = _budget_score(notice.budget)
            f_dday      = _dday_score(notice.deadline_date)
            f_l3        = 1.0 if notice.l3_strong == "Y" else 0.0
            f_industry  = min(sc.industry_score / 100.0, 1.0)

            features = {
                "fitness_score":  f_fitness,
                "priority_score": f_priority,
                "budget_억":      f_budget,
                "dday_urgency":   f_dday,
                "l3_flag":        f_l3,
                "industry_score": f_industry,
            }

            # sklearn 모델 우선, 없으면 룰 기반
            sklearn_prob = self._sklearn_prob(features)
            if sklearn_prob is not None:
                prob = sklearn_prob
            else:
                prob = sum(_WEIGHTS[k] * v for k, v in features.items())

            grade, action = _grade(prob)

            contributions = {k: round(_WEIGHTS[k] * v, 3) for k, v in features.items()}

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
        log.info("[WinPred] 예측 완료: 총 %d건 | A등급 %d건", len(report.predictions), a_cnt)
        return report


# ═══════════════════════════════════════════════════════════════════════════════
# WinPredictionTrainer — sklearn LogisticRegression 학습기
# ═══════════════════════════════════════════════════════════════════════════════

_FEATURE_NAMES = [
    "fitness_score", "priority_score", "budget_억",
    "dday_urgency", "l3_flag", "industry_score",
]


class WinPredictionTrainer:
    """
    SQLite DB + CRM 메모(crm_memos.json)에서 학습 데이터를 구성해
    sklearn LogisticRegression 모델을 학습·저장한다.

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

    # ── 피처 추출 ─────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_features(row: dict) -> Optional[List[float]]:
        """DB 행(dict) → 피처 벡터. 필수값 누락 시 None."""
        try:
            f_fitness  = min(float(row.get("fitness_score",   0) or 0) / 100.0, 1.0)
            f_priority = min(float(row.get("priority_score",  0) or 0) / 100.0, 1.0)
            f_budget   = _budget_score(str(row.get("budget", "") or ""))
            f_dday     = _dday_score(str(row.get("deadline_date", "") or ""))
            f_l3       = 1.0 if str(row.get("l3_strong", "N")) == "Y" else 0.0
            f_industry = min(float(row.get("industry_score", 0) or 0) / 100.0, 1.0)
            return [f_fitness, f_priority, f_budget, f_dday, f_l3, f_industry]
        except Exception:
            return None

    # ── 데이터 로드 ───────────────────────────────────────────────────────────

    def _load_data(self) -> Tuple[List[List[float]], List[int]]:
        """
        (X, y) 반환. y: 1=win, 0=loss
        데이터 소스 우선순위:
          1) crm_memos.json (수주/탈락 실 레이블)
          2) data/exports/training/*.jsonl (파이프라인 자동 C/D 저장)
          3) SQLite DB notices 테이블 (priority_grade 대리 레이블)
        """
        import sqlite3, json as _json

        # ── CRM 메모 true 레이블 ──────────────────────────────────────────────
        true_labels: dict = {}
        if self.memos_path.exists():
            try:
                memos = _json.loads(self.memos_path.read_text(encoding="utf-8"))
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

        # ── JSONL 파일에서 데이터 로드 (최신 파일 우선 — 같은 공고의 최신 등급 반영) ──
        jsonl_dir = self.db_path.parent / "exports" / "training"
        if jsonl_dir.exists():
            for jf in sorted(jsonl_dir.glob("*.jsonl"), reverse=True):
                try:
                    for line in jf.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        rec = _json.loads(line)
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
                            # win_label 우선, 없으면 grade로 판단
                            if "win_label" in rec:
                                lbl = int(rec["win_label"])
                            else:
                                grade = str(rec.get("grade", ""))
                                if grade in ("A", "B"):
                                    lbl = 1
                                elif grade in ("C", "D"):
                                    lbl = 0
                                else:
                                    label_source["skipped"] += 1
                                    continue
                            X.append(feats); y.append(lbl)
                            label_source["jsonl"] += 1
                        seen_ids.add(nid)
                except Exception as exc:
                    log.warning("[Trainer] JSONL 로드 실패 %s: %s", jf.name, exc)

        # ── SQLite DB에서 A/B 데이터 보완 ────────────────────────────────────
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
                    grade = str(row_dict.get("priority_grade", ""))
                    if grade not in ("A", "B", "C", "D"):
                        label_source["skipped"] += 1
                        continue
                    feats = self._extract_features(row_dict)
                    if feats is None:
                        label_source["skipped"] += 1
                        continue
                    lbl = 1 if grade in ("A", "B") else 0
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

    def train(self, min_samples: int = 20) -> dict:
        """
        모델 학습 후 data/models/win_pred_lr.pkl 저장.
        Returns: {"accuracy": float, "cv_mean": float, "n_samples": int, "n_win": int, "model_path": str}
        """
        import numpy as np
        from sklearn.linear_model import LogisticRegression
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

        # 스케일링
        scaler   = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # 교차 검증 — win 샘플 수 기반으로 fold 수 결정
        cv_folds = max(2, min(5, n_win))
        model = LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=42,
            C=1.0,
        )
        try:
            cv_scores = cross_val_score(model, X_scaled, y, cv=cv_folds, scoring="roc_auc")
            cv_mean   = float(cv_scores.mean())
            log.info("[Trainer] CV ROC-AUC: %.3f ± %.3f (%d-fold)", cv_mean, cv_scores.std(), cv_folds)
        except Exception as e:
            log.warning("[Trainer] CV 실패 (%s) → 학습 계속 진행", e)
            cv_mean = 0.0

        # 전체 데이터로 최종 학습
        model.fit(X_scaled, y)

        # 홀드아웃 정확도 — win이 충분할 때만 stratify 사용
        if len(X) >= 30 and n_win >= 2:
            try:
                Xtr, Xte, ytr, yte = train_test_split(
                    X_scaled, y, test_size=0.3, random_state=42,
                    stratify=y if n_win >= 2 else None
                )
                model_eval = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
                model_eval.fit(Xtr, ytr)
                accuracy = float(model_eval.score(Xte, yte))
            except Exception:
                accuracy = cv_mean if cv_mean > 0 else 0.5
        else:
            accuracy = cv_mean if cv_mean > 0 else 0.5

        # 저장
        bundle = {
            "model":         model,
            "scaler":        scaler,
            "feature_names": _FEATURE_NAMES,
            "accuracy":      accuracy,
            "cv_roc_auc":    cv_mean,
            "n_samples":     len(X),
            "n_win":         n_win,
        }
        self.model_out.parent.mkdir(parents=True, exist_ok=True)
        with open(self.model_out, "wb") as f:
            pickle.dump(bundle, f)

        log.info("[Trainer] 모델 저장: %s (accuracy=%.3f)", self.model_out, accuracy)
        return {
            "accuracy":   round(accuracy,  3),
            "cv_roc_auc": round(cv_mean,   3),
            "n_samples":  len(X),
            "n_win":      n_win,
            "model_path": str(self.model_out),
        }
