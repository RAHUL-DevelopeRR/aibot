"""Media player routes - VLC-style video player for lab experiment demonstrations"""
from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

from models.user import Experiment, LabConfig

media_bp = Blueprint('media', __name__)


@media_bp.route('/player/<int:experiment_id>')
@login_required
def player(experiment_id):
    """VLC-style media player for experiment demonstration videos"""
    experiment = Experiment.query.get_or_404(experiment_id)

    if not experiment.video_url:
        flash('No video available for this experiment.', 'info')
        if current_user.role == 'student':
            return redirect(url_for('student.dashboard'))
        return redirect(url_for('teacher.dashboard'))

    lab = LabConfig.query.get(experiment.lab_config_id) or abort(404)

    return render_template('media/player.html',
                         experiment=experiment,
                         lab=lab)


@media_bp.route('/library')
@login_required
def library():
    """Browse all experiments that have video content"""
    experiments = (
        Experiment.query
        .options(joinedload(Experiment.lab_config))
        .filter(Experiment.video_url.isnot(None))
        .filter(Experiment.video_url != '')
        .order_by(Experiment.lab_config_id, Experiment.experiment_no)
        .all()
    )

    labs_data = {}
    for exp in experiments:
        lab = exp.lab_config
        if lab and lab.id not in labs_data:
            labs_data[lab.id] = {
                'lab': lab,
                'experiments': []
            }
        if lab:
            labs_data[lab.id]['experiments'].append(exp)

    return render_template('media/library.html',
                         labs_data=labs_data)
