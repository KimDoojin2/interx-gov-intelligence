import os
import logging

logger = logging.getLogger(__name__)

class DocumentParser:
    def parse(self, file_path: str, ext: str) -> str:
        if not os.path.exists(file_path):
            return ""

        ext = ext.lower().replace(".", "")
        try:
            if ext == "pdf":
                return self._parse_pdf(file_path)
            elif ext in ["hwp", "hwpx"]:
                return self._parse_hwp(file_path)
            else:
                return f"[{ext} 확장자는 텍스트 추출 생략]"
        except Exception as e:
            logger.debug(f"파싱 에러 {file_path}: {e}")
            return ""

    def _parse_pdf(self, file_path: str) -> str:
        try:
            import PyPDF2 # 코랩 기본 내장 또는 가벼운 라이브러리
            text = ""
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                # 속도를 위해 최대 5페이지만 읽기
                for i in range(min(5, len(reader.pages))):
                    page_text = reader.pages[i].extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text[:3000] 
        except Exception:
            return ""

    def _parse_hwp(self, file_path: str) -> str:
        try:
            import olefile
            with olefile.OleFileIO(file_path) as f:
                # HWP 파일 내 '미리보기' 텍스트만 빠르게 추출 (에러 확률 가장 낮음)
                if f.exists("PrvText"):
                    prv_data = f.openstream("PrvText").read()
                    return prv_data.decode("utf-16-le", errors="ignore")[:3000]
        except Exception:
            pass
        return ""
