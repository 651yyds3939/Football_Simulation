function make_matlab_traces(out_file)
%MAKE_MATLAB_TRACES Reference results from the MATLAB code for the Python cross-check.
%
%   make_matlab_traces          writes matlab_traces.json next to this file
%
%   Every scenario runs with all randomness switched off (no kick, odometry
%   or sensor noise), so the MATLAB and Python versions must give the same
%   trajectories. tests/test_matlab_crosscheck.py compares them.

here = fileparts(mfilename('fullpath'));
addpath(fullfile(here, '..', '..', '..'));
setup_paths();
if nargin < 1
    out_file = fullfile(here, 'matlab_traces.json');
end
rng(1);

pp = pitch_params();
bp = ball_params();  bp.kick_sig_dir = 0;  bp.kick_sig_speed = 0;
rp = robot_params(); rp.odo_sig_trans = 0; rp.odo_sig_rot = 0;
perfect = sensor_params(); perfect.mode = 'perfect';
quiet = sensor_params();
quiet.sig_range_rel = 0; quiet.sig_range_abs = 0; quiet.sig_bearing = 0;
quiet.p_miss = 0; quiet.sig_loc_pos = 0; quiet.sig_loc_heading = 0;

% name, roles, robots [x y heading team], ball [x y], ball velocity [vx vy]
sc = {
    'striker v keeper',       {'striker', 'keeper'},            [-1.5 0.5 0 1; 4.15 0 pi 2],              [1.2 -0.8], [0 0]
    'go round the ball',      {'striker'},                      [1 0.2 0 1],                              [0 0],      [0 0]
    'two attackers v keeper', {'striker', 'striker', 'keeper'}, [-1.5 -0.7 0 1; 1.8 1 0 1; 4.15 0 pi 2], [0.8 0.4],  [0 0]
    'pass to a team-mate',    {'striker', 'striker'},           [-0.5 0 0 1; 1.4 -1 pi 1],                [0 0],      [0 0]
    'keeper clears',          {'keeper'},                       [4.15 0 pi 2],                            [3.7 0.4],  [0 0]
    'shot at the keeper',     {'keeper'},                       [4.1 0 pi 2],                             [2.6 0],    [1.9 0.35]
};
modes = {'perfect', perfect; 'quiet', quiet};

traces = {};
for i = 1:size(sc, 1)
    for m = 1:size(modes, 1)
        traces{end + 1} = run_trace(sc(i, :), modes{m, 1}, modes{m, 2}, pp, bp, rp); %#ok<AGROW>
    end
end

% Single values from the ball prediction helpers
[~, ~, t_stop, d_stop] = ball_path([0 0], [1.5 0], 0, bp);
[v_pass, ~] = pass_speed(1.5, bp);
[target, t_meet] = intercept_point([0 0], [1.5 0], [1.2 0.2], rp, bp);
values = struct('t_stop', t_stop, 'd_stop', d_stop, 'pass_speed', v_pass, ...
                'intercept_target', target, 'intercept_time', t_meet);

% The ball demo
demo = demo_pitch_ball(false);
outcomes = {demo.outcome};

out = struct('dt', 0.02, 'traces', {traces}, 'values', values, 'demo_outcomes', {outcomes});
fid = fopen(out_file, 'w');
fprintf(fid, '%s', jsonencode(out));
fclose(fid);
fprintf('MATLAB_TRACES_OK %d traces\n', numel(traces));
end

% ---------------------------------------------------------------------
function trace = run_trace(sc, mode, sp, pp, bp, rp)
roles = sc{2}; start = sc{3}; dt = 0.02;
n = numel(roles);
w = world_init(pp);
clear robots
for k = n:-1:1
    robots(k) = struct('pos', start(k, 1:2), 'heading', start(k, 3), 'team', start(k, 4), 'vel', [0 0]);
end
w.robots = robots;
w.ball.pos = sc{4};
w.ball.vel = sc{5};
ss = sensor_init(n);
rs = robot_state_init(n);
mem = cell(1, n);
P = cell(1, n);
cmds = repmat(walk_cmd(0, 0, 0), 1, n);
outcome = 'timeout';
samples = {};
for step = 1:round(40 / dt)
    for k = 1:n
        [P{k}, ss(k)] = sensor_step(w, k, ss(k), sp, dt, rs(k).odom);
    end
    for k = 1:n
        if strcmp(roles{k}, 'striker')
            [cmds(k), mem{k}] = striker_behaviour(P{k}, mem{k}, w.robots(k).team, pp, bp, rp, rs(k).odom);
        else
            [cmds(k), mem{k}] = goalkeeper_behaviour(P{k}, mem{k}, w.robots(k).team, pp, bp, rp, rs(k).odom);
        end
    end
    finished = false;
    for k = 1:n
        [w.robots(k), rs(k), kick_now] = robot_step(w.robots(k), rs(k), cmds(k), rp, dt);
        if kick_now
            [w.ball, kicked] = ball_kick(w.ball, w.robots(k), k, rs(k).kick_dir, rs(k).kick_speed, bp);
            if kicked && strcmp(roles{k}, 'keeper')
                outcome = 'cleared';
                finished = true;
                break
            end
        end
    end
    if finished
        break
    end
    w.robots = keep_apart(w.robots, pp, rp);
    [w, ev] = world_step(w, pp, bp, dt);
    if ~isempty(ev)
        outcome = ev.type;
        break
    end
    if mod(step, 25) == 0
        poses = zeros(1, 3 * n);
        states = cell(1, n);
        for k = 1:n
            poses(3 * k - 2:3 * k) = [w.robots(k).pos, w.robots(k).heading];
            states{k} = mem{k}.state;
        end
        samples{end + 1} = struct('t', w.t, 'ball', w.ball.pos, 'poses', {num2cell(poses)}, ...
                                  'states', {states}); %#ok<AGROW>
    end
end
trace = struct('name', sc{1}, 'sensors', mode, 'roles', {roles}, ...
               'robots', {num2cell(reshape(start', 1, []))}, 'ball_start', sc{4}, 'ball_vel', sc{5}, ...
               'outcome', outcome, 't_end', w.t, 'samples', {samples});
end
