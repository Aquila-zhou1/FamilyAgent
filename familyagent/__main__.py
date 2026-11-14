"""FamilyAgent FastAPI 应用主入口

可通过 `python -m familyagent` 命令启动服务
"""

import uvicorn
from fastapi import FastAPI

from familyagent.route.dispatch_route import router as dispatch_router
from familyagent.route.health_route import router as health_router
from familyagent.route.travel_route import router as travel_router

# 初始化 FastAPI 应用
app = FastAPI(
    title="家庭智能体服务平台",
    version="0.1.0",
    description="专业的儿童、老人、婴儿健康护理知识助手 + 家庭旅游规划助手",
)

# 注册健康问答路由
app.include_router(health_router)

# 注册旅游规划路由
app.include_router(travel_router)

# 注册智能体分发路由
app.include_router(dispatch_router)

# 关键逻辑：在应用初始化后，应用CDN补丁
import fastapi_cdn_host

fastapi_cdn_host.patch_docs(app)


@app.get("/")
def read_root():
    """根路径 - 服务状态检查"""
    return {
        "message": "家庭智能体 API 服务已启动",
        "health_agent": "/agent/",
        "travel_agent": "/agent/travel",
        "dispatch_agent": "/agent/dispatch",
        "docs": "/docs",
    }


def main():
    """启动 uvicorn 服务"""
    uvicorn.run("familyagent.__main__:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
