"""OCR 识别服务（封装 RapidOCR）。

RapidOCR 是 PaddleOCR 的 ONNX 精简版，免费开源、离线运行、CPU 友好（2C4G 可跑）。
首次调用时会加载模型（数百 MB，需几秒），故采用模块级单例+懒加载。
"""
from __future__ import annotations

import logging
import threading

from app.core.config import settings

logger = logging.getLogger(__name__)


class OcrService:
    """OCR 识别服务封装。"""

    def __init__(self) -> None:
        self._engine = None
        self._lock = threading.Lock()

    def _get_engine(self):
        """懒加载并缓存 RapidOCR 引擎实例（线程安全）。"""
        if self._engine is None:
            with self._lock:
                if self._engine is None:
                    from rapidocr_onnxruntime import RapidOCR

                    logger.info("正在加载 RapidOCR 模型，首次调用可能需要数秒...")
                    self._engine = RapidOCR()
                    logger.info("RapidOCR 模型加载完成")
        return self._engine

    def recognize(self, image_bytes: bytes) -> dict:
        """识别图片字节流，返回标准结果。

        自动进行预处理：解码 -> 灰度化 -> 必要时适度放大，
        以兼容 RGBA/灰度/小尺寸图片，避免原图模式导致 detection 失败。

        返回结构：
        {
            "text": "识别出的全部文字（按行拼接）",
            "lines": [
                {"text": "...", "confidence": 0.99, "box": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]},
                ...
            ]
        }
        空结果时 text=""，lines=[]。
        """
        import io

        from PIL import Image

        engine = self._get_engine()
        # 预处理：bytes -> PIL -> 灰度；对小图适度放大（提升 detection 召回）
        img = Image.open(io.BytesIO(image_bytes))
        # 统一为灰度：避免 RGBA/CMYK 等模式导致的识别失败
        if img.mode != "L":
            img = img.convert("L")
        # 高度过小的图按比例放大（RapidOCR 对小字检测召回较低）
        min_h = 64
        if img.height < min_h:
            scale = min_h / img.height
            new_size = (int(img.width * scale), min_h)
            img = img.resize(new_size, Image.LANCZOS)

        # 转回 bytes 交给 RapidOCR
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        normalized_bytes = buf.getvalue()

        result, elapse = engine(normalized_bytes)
        # 解析结果：result 为 None 表示未识别到文字
        lines: list[dict] = []
        if result is not None:
            # result 形如 [[box, text, score], ...]
            for item in result:
                if len(item) < 3:
                    continue
                box = item[0]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                text = str(item[1])
                score = float(item[2])
                if settings.ocr_return_score:
                    lines.append(
                        {
                            "text": text,
                            "confidence": round(score, 4),
                            "box": self._normalize_box(box),
                        }
                    )
                else:
                    lines.append(
                        {
                            "text": text,
                            "box": self._normalize_box(box),
                        }
                    )

        if settings.ocr_return_details:
            full_text = "\n".join(l["text"] for l in lines)
        else:
            full_text = "".join(l["text"] for l in lines)

        return {"text": full_text, "lines": lines}

    @staticmethod
    def _normalize_box(box) -> list[list[int]]:
        """将坐标规范化，统一转为 int 的 [x,y] 四角点列表。"""
        try:
            return [[int(round(p[0])), int(round(p[1]))] for p in box]
        except (TypeError, ValueError, IndexError):
            return []


# 全局单例
ocr_service = OcrService()
