from flask import Blueprint
# アプリケーションの初期化
main = Blueprint('main', __name__)

from . import routes