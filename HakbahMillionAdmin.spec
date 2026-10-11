# -*- mode: python ; coding: utf-8 -*-
# ملف بناء PyInstaller لمشروع هكبة المليون
# يُنتج ملف EXE واحداً مع جميع الملفات المطلوبة (one-folder)

a = Analysis(
    ['admin_app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # ملفات الواجهة الثابتة (الصور، الأنماط، الخطوط)
        ('static', 'static'),
        # قوالب HTML لخادم الويب الداخلي
        ('templates', 'templates'),
        # وحدات الواجهة الرسومية
        ('gui', 'gui'),
        # برنامج النفق لتشغيل الموقع عبر الإنترنت
        ('cloudflared.exe', '.'),
        # قاعدة البيانات الافتراضية (إن وجدت)
        # ('hakbah.db', '.'),  # احذف التعليق إذا أردت تضمينها
    ],
    hiddenimports=[
        # uvicorn — خادم ASGI الداخلي
        'uvicorn',
        'uvicorn.main',
        'uvicorn.config',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.http.httptools_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.websockets_impl',
        'uvicorn.protocols.websockets.wsproto_impl',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        # FastAPI
        'fastapi',
        'fastapi.middleware',
        'fastapi.middleware.cors',
        'starlette',
        'starlette.middleware',
        'starlette.middleware.sessions',
        'starlette.staticfiles',
        'starlette.templating',
        # قاعدة البيانات
        'sqlalchemy',
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.orm',
        'sqlite3',
        # واجهة المستخدم
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        # المكتبات العربية والنصية
        'arabic_reshaper',
        'bidi',
        'bidi.algorithm',
        # PDF
        'reportlab',
        'reportlab.pdfgen',
        'reportlab.pdfbase.ttfonts',
        'reportlab.lib.pagesizes',
        # Excel
        'pandas',
        'xlsxwriter',
        # الأمان
        'bcrypt',
        'passlib',
        # البريد الإلكتروني
        'email.mime.multipart',
        'email.mime.text',
        # الشبكة
        'requests',
        'h11',
        'httptools',
        'websockets',
        'wsproto',
        # jinja2 للقوالب
        'jinja2',
        'jinja2.ext',
        # أخرى
        'multipart',
        'itsdangerous',
        'anyio',
        'anyio._backends._asyncio',
        'anyio._backends._trio',
        'secrets',
        'ctypes',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # استبعاد ما لا يلزم لتقليل الحجم
        'customtkinter',
        'tkinter',
        'matplotlib',
        'scipy',
        'numpy.distutils',
        'IPython',
        'jupyter',
        'notebook',
    ],
    noarchive=False,
    optimize=1,  # تحسين خفيف للأداء
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # يُخرج الملفات الثنائية إلى مجلد منفصل (one-folder)
    name='HakbahMillionAdmin',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        'vcruntime140.dll',
        'python3*.dll',
        'Qt6*.dll',
    ],
    console=False,  # بدون نافذة console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='static\\logo.ico',
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[
        'vcruntime140.dll',
        'python3*.dll',
        'Qt6*.dll',
    ],
    name='HakbahMillionAdmin',
)
