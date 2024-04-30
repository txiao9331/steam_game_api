# http://localhost:5000/steam_docs/

from flask import Flask, abort, request, render_template
import pymysql
import os
import math
from collections import defaultdict
from flask_swagger_ui import get_swaggerui_blueprint
# from flask_restplus import Api, Resource, Namespace
import json

app = Flask(__name__)

swaggerui_blueprint = get_swaggerui_blueprint(
    base_url='/steam_docs',
    api_url='/static/steamapi.yaml',
)
app.register_blueprint(swaggerui_blueprint)


def load_config():
    with open('config.json') as config_file:
        return json.load(config_file)

def create_db_conn():
    config = load_config()
    db_conn = pymysql.connect(host="localhost",
                            user="root",
                            password=config.get('MYSQL_PASSWORD'),
                            database="steam_store_games",
                            cursorclass=pymysql.cursors.DictCursor)
    return db_conn

@app.route('/v1')
def index():
    return render_template('index.html')

@app.route("/v1/games/<int:game_id>")
def game(game_id):
    include_details = int(request.args.get('include_details', 0)) 
    db_conn=create_db_conn()
    with db_conn.cursor() as cursor:
        cursor.execute("""
                        select 
                            name as Title,
                            g.appid,
                            release_date,
                            developer,
                            genres,
                            steamspy_tags as tags,
                            price,
                            achievements,
                            platforms,
                            short_description as description,
                        case 
                            when required_age = 0 then False
                            else True
                        end as isRequiredAge,
                        case 
                            when english = 1 then True
                            else False
                        end as isEnglish
                        from games g
                        join description d
                        on g.appid = d.steam_appid
                        where g.appid=%s
            """,(game_id,))
        game = cursor.fetchone()

        if game:
            game['isRequiredAge'] = bool(game['isRequiredAge'])
            game['isEnglish'] = bool(game['isEnglish'])
            game = remove_null_fields(game)
        else:
            abort(404)

        if include_details:
            # fetch more information
            cursor.execute("""
                            select
                                positive_ratings,
                                negative_ratings,
                                categories
                            from games 
                            where appid=%s
                            """,(game_id,))
            more_info = cursor.fetchone()
            if more_info:
                # fetch the support_info
                cursor.execute("""
                                select 
                                    website,
                                    support_email,
                                    support_url
                                from support_info where steam_appid=%s""",(game_id,))
                support=cursor.fetchone()
                if support:
                    more_info['support'] = remove_null_fields(support)
                else:
                    more_info['support'] = {}
        else:
            more_info = {}

        game['more_info'] = more_info

        # game = remove_null_fields(game)

    db_conn.close()
    return game
    # formatted_game = "\n".join([f'<p>"{key}": {value}</p>' for key, value in game.items()])
    # return "<div>" + formatted_game + "</div>"

@app.route("/v1/games/<int:game_id>",methods=['DELETE'])
def delete_game(game_id):
    try:
        db_conn=create_db_conn()
        if find_game(game_id):
            with db_conn.cursor() as cursor:
                cursor.execute("DELETE FROM games WHERE appid = %s", (game_id,))
                cursor.execute("DELETE FROM description WHERE steam_appid = %s", (game_id,))
                cursor.execute("DELETE FROM support_info WHERE steam_appid = %s", (game_id,))
            db_conn.commit()
            result = "Game deleted successfully"
        else:
            abort(404)
        return result
    finally:
        db_conn.close()

MAX_PAGE_SIZE = 30

@app.route("/v1/games")
def games():
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', MAX_PAGE_SIZE))
    page_size = min(page_size, MAX_PAGE_SIZE)
    include_details = int(request.args.get('include_details', 0)) 
    db_conn=create_db_conn()

    with db_conn.cursor() as cursor:
        cursor.execute("""
                        select 
                            name as Title,
                            g.appid,
                            release_date,
                            developer,
                            genres,
                            steamspy_tags as tags,
                            price,
                            achievements,
                            platforms,
                            short_description,
                        case 
                            when required_age = 0 then False
                            else True
                        end as isRequiredAge,
                        case 
                            when english = 1 then True
                            else False
                        end as isEnglish 
                        from games g
                        join description d
                        on g.appid = d.steam_appid
                        LIMIT %s OFFSET %s
        """,(page_size, (page - 1) * page_size))
        games = cursor.fetchall()
        games = [remove_null_fields(game) for game in games]
        for game in games:
            game['isRequiredAge'] = bool(game['isRequiredAge'])
            game['isEnglish'] = bool(game['isEnglish'])

        game_ids = [game['appid'] for game in games]

        more_infos_dict = defaultdict(list)

        if include_details:
            cursor.execute("""
                            select
                                appid,
                                positive_ratings,
                                negative_ratings,
                                categories
                            from games 
                            where appid in (%s)
                            """ % ','.join(['%s'] * len(game_ids)), game_ids)
            more_infos = cursor.fetchall()
            for info in more_infos:
                more_info = remove_null_fields(info)
                # more_infos_dict[info['appid']].append(more_info)
                # fetch the support_info
                cursor.execute("""
                                select 
                                    steam_appid,
                                    website,
                                    support_email,
                                    support_url
                                from support_info where steam_appid in (%s)
                                """% ','.join(['%s'] * len(game_ids)), game_ids)
                supports=cursor.fetchall()   
                for support in supports:
                    more_info['support'] = remove_null_fields(support)

                more_infos_dict[info['appid']].append(more_info)

        for game in games:
            game['more_info'] = more_infos_dict.get(game['appid'], [])

    query = "SELECT COUNT(*) AS total FROM games"  
    last_page = get_last_page(query,page_size)

    db_conn.close() 

    return {
        'games': games,
        'next_page': f'/games?page={page+1}&page_size={page_size}&include_details={include_details}',
        'last_page': f'/games?page={last_page}&page_size={page_size}&include_details={include_details}',
    }

@app.route("/v1/games",methods=["POST"])
def post_game():
    try:
        db_conn=create_db_conn()
        new_game = request.json
        appid=new_game['appid']
        if find_game(appid):
            result = "Game already exists"
        else:
            result = add_new_game(new_game)
        return result
    finally:
        db_conn.close()

@app.route("/v1/games",methods=['PUT'])
def update_game():
    pass

def add_new_game(game_data):
    db_conn=create_db_conn()
    with db_conn.cursor() as cursor:
        sql = """INSERT INTO games 
                    (appid, name, release_date, english, developer, platforms, 
                    required_age, categories, genres, steamspy_tags, 
                    achievements, positive_ratings, negative_ratings, price) 
                    VALUES 
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

        cursor.execute(sql, (
                game_data['appid'], game_data['name'], game_data['release_date'], 
                game_data['english'], game_data['developer'], game_data['platforms'], 
                game_data['required_age'], game_data['categories'], game_data['genres'], 
                game_data['tags'], game_data['achievements'], 
                game_data['positive_ratings'], game_data['negative_ratings'], 
                game_data['price']
            ))
        
        sql2 = """INSERT INTO description (steam_appid, short_description)
                VALUES (%s, %s)"""
        cursor.execute (sql2,(game_data['appid'],game_data['short_description']))

        sql3 = """INSERT INTO support_info
                    (steam_appid,website,support_url,support_email)
                    VALUES (%s,%s,%s,%s)"""
        cursor.execute (sql3,(game_data['appid'],game_data['website'],game_data['support_url'],game_data['support_email']))

        db_conn.commit()
        db_conn.close()
    
    return "New game added successfully"

def find_game (appid):
    try:
        db_conn=create_db_conn()
        with db_conn.cursor() as cursor:
            cursor.execute("SELECT * FROM games WHERE appid = %s", (appid,))
            game = cursor.fetchone()
            if game:
                return True
            else:
                return False
    finally:
        db_conn.close()

def remove_null_fields(obj):
    return {k:v for k, v in obj.items() if v is not None}

def get_last_page(query,page_size):
    db_conn=create_db_conn()
    with db_conn.cursor() as cursor:
        cursor.execute(query)    
        total = cursor.fetchone()
        last_page = math.ceil(total['total'] / page_size)
    db_conn.close()
    return last_page   


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)