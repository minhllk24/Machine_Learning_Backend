import sys
import uvicorn
from app.config import settings

# Đảm bảo in UTF-8 không lỗi console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

if __name__ == '__main__':
    print("=" * 60)
    print(f" KHỞI CHẠY BACKEND MACHINE LEARNING - DỮ LIỆU ONLINE RETAIL")
    print(f" URL API Server: http://{settings.HOST}:{settings.PORT}")
    print(f" Swagger UI Docs: http://{settings.HOST}:{settings.PORT}/docs")
    print(f" Database: {settings.DB_NAME} @ {settings.DB_HOST}:{settings.DB_PORT}")
    print("=" * 60)
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
