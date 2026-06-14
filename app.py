from flask import Flask
from config import Config
from database import init_db
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.chw import chw_bp
from routes.supervisor import supervisor_bp
from routes.dho import dho_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(chw_bp)
    app.register_blueprint(supervisor_bp)
    app.register_blueprint(dho_bp)

    with app.app_context():
        init_db()

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=Config.DEBUG)