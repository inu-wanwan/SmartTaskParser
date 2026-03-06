from abc import ABC

class BaseService(ABC):
    """
    すべてのビジネスロジック（Service）の基底クラス。
    """
    def __init__(self):
        # 必要に応じて共通の初期化処理を記述
        pass