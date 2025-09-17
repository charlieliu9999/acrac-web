from celery import Celery
from app.core.config import settings

# 创建Celery实例
celery_app = Celery(
    "acrac_ragas",
    broker=settings.CELERY_BROKER_URL,
    backend=None,  # 暂时禁用结果后端
    include=["app.tasks.ragas_tasks"]
)

# Celery配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30分钟超时
    task_soft_time_limit=25 * 60,  # 25分钟软超时
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    task_ignore_result=True,  # 忽略结果，避免序列化问题
)

# 任务路由配置
celery_app.conf.task_routes = {
    "app.tasks.ragas_tasks.*": {"queue": "ragas_queue"},
}

if __name__ == "__main__":
    celery_app.start()