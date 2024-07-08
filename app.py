import os
import re
import json
import mimetypes
from fuzzywuzzy import fuzz
from mutagen.mp4 import MP4
from pathlib import Path
from flask import Flask, request, jsonify, render_template
from models import db, Site, Scene
from PIL import Image
import imagehash

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jizzarr.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Create tables before the first request
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/collection')
def collection():
    return render_template('collection.html')

@app.route('/collection_data', methods=['GET'])
def collection_data():
    sites = Site.query.all()
    collection = []
    for site in sites:
        scenes = Scene.query.filter_by(site_id=site.id).all()
        scene_list = []
        for scene in scenes:
            scene_list.append({
                'id': scene.id,
                'title': scene.title,
                'date': scene.date,
                'duration': scene.duration,
                'image': scene.image,
                'performers': scene.performers,
                'status': scene.status,
                'local_path': scene.local_path
            })
        collection.append({
            'site': {
                'uuid': site.uuid,
                'name': site.name,
                'url': site.url,
                'description': site.description,
                'rating': site.rating,
                'network': site.network,
                'parent': site.parent,
                'logo': site.logo,
                'home_directory': site.home_directory
            },
            'scenes': scene_list
        })
    return jsonify(collection)

@app.route('/add_site', methods=['POST'])
def add_site():
    data = request.json
    site_uuid = data['site']['uuid']

    existing_site = Site.query.filter_by(uuid=site_uuid).first()

    rating = data['site']['rating']
    if rating == '':
        rating = None
    else:
        try:
            rating = float(rating)
        except ValueError:
            rating = None

    if existing_site:
        existing_site.name = data['site']['name']
        existing_site.url = data['site']['url']
        existing_site.description = data['site']['description']
        existing_site.rating = rating
        existing_site.network = data['site']['network']
        existing_site.parent = data['site']['parent']
        existing_site.logo = data['site'].get('logo', '')

        Scene.query.filter_by(site_id=existing_site.id).delete()
        scenes = []
        for scene_data in data['scenes']:
            scene = Scene(
                site_id=existing_site.id,
                title=scene_data['title'],
                date=scene_data['date'],
                duration=scene_data['duration'],
                image=scene_data['image'],
                performers=scene_data['performers']
            )
            scenes.append(scene)
        db.session.bulk_save_objects(scenes)
        db.session.commit()

        return jsonify({'message': 'Site and scenes updated successfully!'}), 200
    else:
        site = Site(
            uuid=site_uuid,
            name=data['site']['name'],
            url=data['site']['url'],
            description=data['site']['description'],
            rating=rating,
            network=data['site']['network'],
            parent=data['site']['parent'],
            logo=data['site'].get('logo', '')
        )
        db.session.add(site)
        db.session.commit()

        scenes = []
        for scene_data in data['scenes']:
            scene = Scene(
                site_id=site.id,
                title=scene_data['title'],
                date=scene_data['date'],
                duration=scene_data['duration'],
                image=scene_data['image'],
                performers=scene_data['performers']
            )
            scenes.append(scene)
        db.session.bulk_save_objects(scenes)
        db.session.commit()

        return jsonify({'message': 'Site and scenes added successfully!'}), 201

@app.route('/remove_site/<string:site_uuid>', methods=['DELETE'])
def remove_site(site_uuid):
    site = Site.query.filter_by(uuid=site_uuid).first()
    if not site:
        return jsonify({'error': 'Site not found'}), 404

    Scene.query.filter_by(site_id=site.id).delete()
    db.session.delete(site)
    db.session.commit()

    return jsonify({'message': 'Site and scenes removed successfully!'})

@app.route('/remove_scene/<int:scene_id>', methods=['DELETE'])
def remove_scene(scene_id):
    scene = db.session.get(Scene, scene_id)
    if not scene:
        return jsonify({'error': 'Scene not found'}), 404

    db.session.delete(scene)
    db.session.commit()

    return jsonify({'message': 'Scene removed successfully!'})

@app.route('/match_scene', methods=['POST'])
def match_scene():
    data = request.json
    scene_id = data.get('scene_id')
    file_path = data.get('file_path')

    scene = db.session.get(Scene, scene_id)
    if not scene:
        return jsonify({'error': 'Scene not found'}), 404

    scene.local_path = file_path
    scene.status = 'Found'
    db.session.commit()
    return jsonify({'message': 'Scene matched successfully!'})

@app.route('/set_home_directory', methods=['POST'])
def set_home_directory():
    data = request.json
    site_uuid = data.get('site_uuid')
    directory = data.get('directory')

    site = Site.query.filter_by(uuid=site_uuid).first()
    if not site:
        return jsonify({'error': 'Site not found'}), 404

    site.home_directory = directory
    db.session.commit()

    return jsonify({'message': 'Home directory set successfully!'})

def get_file_duration(file_path):
    try:
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension == '.mp4':
            audio = MP4(file_path)
            return audio.info.length / 60  # convert seconds to minutes
        # Add more formats if necessary
    except Exception as e:
        print(f"Error getting duration for file {file_path}: {e}")
    return None

def clean_string(input_string):
    return re.sub(r'[^\w\s]', '', input_string).lower()

def get_phash(image_path):
    try:
        with Image.open(image_path) as img:
            return imagehash.phash(img)
    except Exception as e:
        print(f"Error generating phash for file {image_path}: {e}")
    return None

def get_potential_matches(scenes, filenames, tolerance=95):
    potential_matches = []
    for scene in scenes:
        for filename in filenames:
            clean_filename = clean_string(str(filename))
            clean_scene_title = clean_string(scene['title'])
            if fuzz.partial_ratio(clean_filename, clean_scene_title) >= tolerance:
                match_data = {
                    'scene_id': scene['id'],
                    'suggested_file': str(filename),
                    'title_score': fuzz.partial_ratio(clean_filename, clean_scene_title),
                }
                if 'date' in scene and scene['date']:
                    clean_scene_date = clean_string(scene['date'])
                    if fuzz.partial_ratio(clean_filename, clean_scene_date) >= tolerance:
                        match_data['date_score'] = fuzz.partial_ratio(clean_filename, clean_scene_date)
                if 'duration' in scene and scene['duration']:
                    file_duration = get_file_duration(str(filename))
                    if file_duration and abs(file_duration - scene['duration']) < 1:  # tolerance of 1 minute
                        match_data['duration_score'] = 100
                potential_matches.append(match_data)
    return potential_matches


@app.route('/suggest_matches', methods=['POST'])
def suggest_matches():
    data = request.json
    site_uuid = data.get('site_uuid')
    tolerance = data.get('tolerance', 95)

    site = Site.query.filter_by(uuid=site_uuid).first()
    if not site or not site.home_directory:
        return jsonify({'error': 'Site or home directory not found'}), 404

    scenes = Scene.query.filter_by(site_id=site.id).all()
    scene_data = [{'id': scene.id, 'title': scene.title, 'date': scene.date, 'duration': scene.duration} for scene in scenes]

    home_directory = Path(site.home_directory)
    filenames = [f for f in home_directory.glob('**/*') if f.is_file()]

    potential_matches = get_potential_matches(scene_data, filenames, tolerance)
    return jsonify(potential_matches)

if __name__ == '__main__':
    app.run(debug=True)
