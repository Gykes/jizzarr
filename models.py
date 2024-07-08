from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Site(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(255))
    description = db.Column(db.Text)
    rating = db.Column(db.String(32)) 
    network = db.Column(db.String(100))
    parent = db.Column(db.String(100))
    logo = db.Column(db.String(255))  
    home_directory = db.Column(db.String(255)) 

    scenes = db.relationship('Scene', backref='site', lazy=True)

class Scene(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('site.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    date = db.Column(db.String(50))
    duration = db.Column(db.Integer)
    image = db.Column(db.String(255))
    performers = db.Column(db.String(255))
    status = db.Column(db.String(50))
    local_path = db.Column(db.String(255))
