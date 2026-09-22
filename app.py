import os
from datetime import datetime, timedelta
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)
app.config['SECRET_KEY'] = 'clave_secreta_super_segura_nfl'

# Configuración inteligente de Base de Datos (SQLite local / PostgreSQL en Render)
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
  database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = (
    database_url or 'sqlite:///quiniela.db'
)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'



# --- DICCIONARIO OFICIAL DE LOS 32 EQUIPOS NFL Y SUS LOGOS ---
NFL_TEAMS = {
    'Arizona Cardinals': 'https://a.espncdn.com/i/teamlogos/nfl/500/ari.png',
    'Atlanta Falcons': 'https://a.espncdn.com/i/teamlogos/nfl/500/atl.png',
    'Baltimore Ravens': 'https://a.espncdn.com/i/teamlogos/nfl/500/bal.png',
    'Buffalo Bills': 'https://a.espncdn.com/i/teamlogos/nfl/500/buf.png',
    'Carolina Panthers': 'https://a.espncdn.com/i/teamlogos/nfl/500/car.png',
    'Chicago Bears': 'https://a.espncdn.com/i/teamlogos/nfl/500/chi.png',
    'Cincinnati Bengals': 'https://a.espncdn.com/i/teamlogos/nfl/500/cin.png',
    'Cleveland Browns': 'https://a.espncdn.com/i/teamlogos/nfl/500/cle.png',
    'Dallas Cowboys': 'https://a.espncdn.com/i/teamlogos/nfl/500/dal.png',
    'Denver Broncos': 'https://a.espncdn.com/i/teamlogos/nfl/500/den.png',
    'Detroit Lions': 'https://a.espncdn.com/i/teamlogos/nfl/500/det.png',
    'Green Bay Packers': 'https://a.espncdn.com/i/teamlogos/nfl/500/gb.png',
    'Houston Texans': 'https://a.espncdn.com/i/teamlogos/nfl/500/hou.png',
    'Indianapolis Colts': 'https://a.espncdn.com/i/teamlogos/nfl/500/ind.png',
    'Jacksonville Jaguars': 'https://a.espncdn.com/i/teamlogos/nfl/500/jax.png',
    'Kansas City Chiefs': 'https://a.espncdn.com/i/teamlogos/nfl/500/kc.png',
    'Las Vegas Raiders': 'https://a.espncdn.com/i/teamlogos/nfl/500/lv.png',
    'Los Angeles Chargers': 'https://a.espncdn.com/i/teamlogos/nfl/500/lac.png',
    'Los Angeles Rams': 'https://a.espncdn.com/i/teamlogos/nfl/500/lar.png',
    'Miami Dolphins': 'https://a.espncdn.com/i/teamlogos/nfl/500/mia.png',
    'Minnesota Vikings': 'https://a.espncdn.com/i/teamlogos/nfl/500/min.png',
    'New England Patriots': 'https://a.espncdn.com/i/teamlogos/nfl/500/ne.png',
    'New Orleans Saints': 'https://a.espncdn.com/i/teamlogos/nfl/500/no.png',
    'New York Giants': 'https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png',
    'New York Jets': 'https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png',
    'Philadelphia Eagles': 'https://a.espncdn.com/i/teamlogos/nfl/500/phi.png',
    'Pittsburgh Steelers': 'https://a.espncdn.com/i/teamlogos/nfl/500/pit.png',
    'San Francisco 49ers': 'https://a.espncdn.com/i/teamlogos/nfl/500/sf.png',
    'Seattle Seahawks': 'https://a.espncdn.com/i/teamlogos/nfl/500/sea.png',
    'Tampa Bay Buccaneers': 'https://a.espncdn.com/i/teamlogos/nfl/500/tb.png',
    'Tennessee Titans': 'https://a.espncdn.com/i/teamlogos/nfl/500/ten.png',
    'Washington Commanders': 'https://a.espncdn.com/i/teamlogos/nfl/500/wsh.png',
}


class User(UserMixin, db.Model):
  id = db.Column(db.Integer, primary_key=True)
  username = db.Column(db.String(150), unique=True, nullable=False)
  password = db.Column(db.String(150), nullable=False)
  is_admin = db.Column(db.Boolean, default=False)
  has_paid = db.Column(db.Boolean, default=False)  # <-- NUEVA COLUMNA DE PAGO

class Match(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  week = db.Column(db.Integer, nullable=False)
  home_team = db.Column(db.String(100), nullable=False)
  home_logo = db.Column(db.String(250), nullable=False)
  home_score = db.Column(db.Integer, default=0)
  away_team = db.Column(db.String(100), nullable=False)
  away_logo = db.Column(db.String(250), nullable=False)
  away_score = db.Column(db.Integer, default=0)
  deadline = db.Column(db.DateTime, nullable=False)
  status = db.Column(db.String(20), default='scheduled')


class Prediction(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
  match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=False)
  chosen_team = db.Column(db.String(100), nullable=False)

# --- PARCHE AUTOMÁTICO Y ADMIN INICIAL (CORRE SIEMPRE AL INICIAR) ---
with app.app_context():
  db.create_all()
  try:
    with db.engine.connect() as connection:
      connection.execute(
          text('ALTER TABLE user ADD COLUMN has_paid BOOLEAN DEFAULT 0;')
      )
      connection.commit()
  except Exception:
    pass  # Si la columna ya existe, la ignora sin problema

  if not User.query.filter_by(username='admin').first():
    admin_user = User(username='admin', password='adminpassword', is_admin=True)
    db.session.add(admin_user)
    db.session.commit()

@login_manager.user_loader
def load_user(user_id):
  return User.query.get(int(user_id))


# --- RUTAS DE AUTENTICACIÓN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
  if request.method == 'POST':
    username = request.form.get('username')
    password = request.form.get('password')
    user = User.query.filter_by(username=username).first()
    if user and user.password == password:
      login_user(user)
      return redirect(url_for('index'))
    flash('Usuario o contraseña incorrectos', 'danger')
  return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
  if request.method == 'POST':
    username = request.form.get('username').strip()
    password = request.form.get('password')

    if not username or not password:
      flash('Por favor completa todos los campos.', 'danger')
      return redirect(url_for('register'))

    if User.query.filter_by(username=username).first():
      flash(
          'El nombre de usuario ya está registrado. Elige otro o contacta'
          ' al admin.',
          'danger',
      )
      return redirect(url_for('register'))

    new_user = User(username=username, password=password, is_admin=False)
    db.session.add(new_user)
    db.session.commit()
    login_user(new_user)
    flash('¡Registro exitoso! Bienvenido a la quiniela.', 'success')
    return redirect(url_for('index'))
  return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
  logout_user()
  return redirect(url_for('login'))


# --- RUTA PRINCIPAL ---
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
  current_week = int(request.args.get('week', 2))
  matches = Match.query.filter_by(week=current_week).all()

  deadline_passed = False
  deadline_date = None
  if matches:
    deadline_date = matches[0].deadline
    if datetime.now() >= deadline_date:
      deadline_passed = True

  if request.method == 'POST':
    if deadline_passed:
      flash('El tiempo límite para registrar pronósticos ha expirado.', 'danger')
      return redirect(url_for('index', week=current_week))

    for key, value in request.form.items():
      if key.startswith('match_'):
        match_id = int(key.split('_')[1])
        chosen_team = value
        pred = Prediction.query.filter_by(
            user_id=current_user.id, match_id=match_id
        ).first()
        if pred:
          pred.chosen_team = chosen_team
        else:
          new_pred = Prediction(
              user_id=current_user.id,
              match_id=match_id,
              chosen_team=chosen_team,
          )
          db.session.add(new_pred)
    db.session.commit()
    flash('¡Tus pronósticos se han guardado con éxito!', 'success')
    return redirect(url_for('index', week=current_week))

  user_preds = {
      p.match_id: p.chosen_team
      for p in Prediction.query.filter_by(user_id=current_user.id).all()
  }

  return render_template(
      'dashboard.html',
      matches=matches,
      user_preds=user_preds,
      week=current_week,
      deadline_passed=deadline_passed,
      deadline_date=deadline_date,
  )


# --- TABLA DE RESULTADOS Y MATRIZ DETALLADA ---
@app.route('/leaderboard')
@login_required
def leaderboard():
  current_week = int(request.args.get('week', 2))
  matches = Match.query.filter_by(week=current_week).all()
  match_dict = {m.id: m for m in matches}

  # Calcular si el deadline de la semana ya pasó (el primer partido marca el cierre)
  deadline_passed = False
  if matches:
    first_match_deadline = min(m.deadline for m in matches)
    if datetime.now() >= first_match_deadline:
      deadline_passed = True

  # Excluir al usuario 'admin' de la lista de participantes por ética
  users = User.query.filter(User.username != 'admin').all()
  scores = []

  for u in users:
    correct_count = 0
    total_predicted = 0
    user_match_choices = {}

    preds = Prediction.query.filter_by(user_id=u.id).all()
    for p in preds:
      match = match_dict.get(p.match_id)
      if match:
        choice = 'L' if p.chosen_team == match.home_team else 'V'

        # CANDADO: Solo mostrar el pronóstico de otros si ya pasó el deadline,
        # o si es el propio usuario actual.
        if deadline_passed or u.id == current_user.id:
          user_match_choices[p.match_id] = choice
        else:
          user_match_choices[p.match_id] = (
              '🔒'  # Símbolo de oculto antes de que inicie la jornada
          )

        if match.status == 'final':
          total_predicted += 1
          winner = None
          if match.home_score > match.away_score:
            winner = match.home_team
          elif match.away_score > match.home_score:
            winner = match.away_team
          if winner and p.chosen_team == winner:
            correct_count += 1

    scores.append({
        'username': u.username,
        'correct': correct_count,
        'total': total_predicted,
        'choices': user_match_choices,
    })

  scores = sorted(scores, key=lambda x: x['correct'], reverse=True)

  max_correct = -1
  if scores:
    max_correct = scores[0]['correct']

  master_results = {}
  for m in matches:
    if m.status == 'final':
      if m.home_score > m.away_score:
        master_results[m.id] = 'L'
      elif m.away_score > m.home_score:
        master_results[m.id] = 'V'
      else:
        master_results[m.id] = 'E'

  return render_template(
      'leaderboard.html',
      scores=scores,
      week=current_week,
      matches=matches,
      match_dict=match_dict,
      max_correct=max_correct,
      master_results=master_results,
      deadline_passed=deadline_passed,
  )


# --- PANEL DE ADMINISTRACIÓN VISUAL ---
@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
  if not current_user.is_admin:
    flash('Acceso denegado', 'danger')
    return redirect(url_for('index'))

  current_week = int(request.args.get('week', 2))

  if request.method == 'POST':
    action = request.form.get('action')

    if action == 'add_match':
      week = int(request.form.get('week', 2))
      home_team = request.form.get('home_team')
      away_team = request.form.get('away_team')
      deadline_str = request.form.get('deadline')

      if not home_team or not away_team:
        flash('Debes seleccionar un equipo Local y un Visitante.', 'danger')
      elif home_team == away_team:
        flash('El equipo local y visitante no pueden ser el mismo.', 'danger')
      else:
        existing_matches = Match.query.filter_by(week=week).all()
        if existing_matches:
          deadline_date = existing_matches[0].deadline
        else:
          if not deadline_str:
            flash(
                'Al ser el primer partido de la semana, debes especificar la'
                ' fecha y hora límite de cierre.',
                'danger',
            )
            return redirect(url_for('admin', week=current_week))
          deadline_date = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')

        new_match = Match(
            week=week,
            home_team=home_team,
            home_logo=NFL_TEAMS[home_team],
            away_team=away_team,
            away_logo=NFL_TEAMS[away_team],
            deadline=deadline_date,
            status='scheduled',
        )
        db.session.add(new_match)
        db.session.commit()
        flash(
            f'Encuentro añadido a la Semana {week}: {home_team} (Local) vs'
            f' {away_team} (Visitante).',
            'success',
        )
      return redirect(url_for('admin', week=week))

    elif action == 'update_score':
      match_id = int(request.form.get('match_id'))
      home_score = int(request.form.get('home_score', 0))
      away_score = int(request.form.get('away_score', 0))

      match = Match.query.get(match_id)
      if match:
        match.home_score = home_score
        match.away_score = away_score
        match.status = 'final'
        db.session.commit()
        flash('Marcador actualizado correctamente.', 'success')
      return redirect(url_for('admin', week=current_week) + '#scores-section')

    elif action == 'delete_match':
      match_id = int(request.form.get('match_id'))
      Prediction.query.filter_by(match_id=match_id).delete()
      Match.query.filter_by(id=match_id).delete()
      db.session.commit()
      flash('Partido eliminado correctamente.', 'success')
      return redirect(url_for('admin', week=current_week) + '#scores-section')

    elif action == 'add_user':
      new_username = request.form.get('new_username').strip()
      new_password = request.form.get('new_password')

      if not new_username or not new_password:
        flash('Completa el usuario y contraseña del participante.', 'danger')
      elif User.query.filter_by(username=new_username).first():
        flash(
            f'El usuario "{new_username}" ya existe en el sistema.', 'danger'
        )
      else:
        user_created = User(
            username=new_username, password=new_password, is_admin=False
        )
        db.session.add(user_created)
        db.session.commit()
        flash(
            f'Participante "{new_username}" registrado exitosamente.',
            'success',
        )
      return redirect(url_for('admin', week=current_week) + '#users-section')

    elif action == 'edit_user':
      user_id = int(request.form.get('user_id'))
      new_pass = request.form.get('edit_password')
      user_to_edit = User.query.get(user_id)

      if user_to_edit and new_pass:
        user_to_edit.password = new_pass
        db.session.commit()
        flash(
            f'Contraseña actualizada para el usuario'
            f' "{user_to_edit.username}".',
            'success',
        )
      return redirect(url_for('admin', week=current_week) + '#users-section')

    elif action == 'delete_user':
      user_id = int(request.form.get('user_id'))
      user_to_del = User.query.get(user_id)
      if user_to_del and user_to_del.username != 'admin':
        Prediction.query.filter_by(user_id=user_id).delete()
        db.session.delete(user_to_del)
        db.session.commit()
        flash('Participante eliminado correctamente.', 'success')
      else:
        flash('No se puede eliminar al administrador principal.', 'danger')
      return redirect(url_for('admin', week=current_week) + '#users-section')

    elif action == 'toggle_payment':
      user_id = int(request.form.get('user_id'))
      user_to_toggle = User.query.get(user_id)
      if user_to_toggle and user_to_toggle.username != 'admin':
        user_to_toggle.has_paid = not user_to_toggle.has_paid
        db.session.commit()
        estado = 'Pagado' if user_to_toggle.has_paid else 'Pendiente'
        flash(
            f'Estatus de pago para "{user_to_toggle.username}" cambiado a:'
            f' {estado}.',
            'success',
        )
      return redirect(url_for('admin', week=current_week) + '#users-section')

    elif action == 'reopen_match':
      match_id = int(request.form.get('match_id'))
      match = Match.query.get(match_id)
      if match:
        match.status = 'scheduled'
        db.session.commit()
        flash(
            f'Encuentro {match.home_team} vs {match.away_team} reabierto con'
            ' éxito.',
            'success',
        )
      return redirect(url_for('admin', week=current_week) + '#scores-section')

  # Filtrar los partidos estrictamente por la semana seleccionada
  matches = (
      Match.query.filter_by(week=current_week)
      .order_by(Match.id.asc())
      .all()
  )
  users_list = User.query.filter(User.username != 'admin').all()

  return render_template(
      'admin.html',
      matches=matches,
      teams_dict=NFL_TEAMS,
      users_list=users_list,
      week=current_week,
  )

if __name__ == '__main__':
  app.run(debug=True)