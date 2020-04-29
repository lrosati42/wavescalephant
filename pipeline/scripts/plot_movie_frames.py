import os
import sys
import argparse
import matplotlib.pyplot as plt
import numpy as np
import scipy
from utils import AnalogSignal2ImageSequence, none_or_float, load_neo, save_plot

def get_events(events, frame_times, event_name='Transitions'):
    trans_events = [ev for ev in events if ev.name == event_name]
    if len(trans_events):
        event = trans_events[0]
        ups = np.array([(t,
                         event.array_annotations['x_coords'][i],
                         event.array_annotations['y_coords'][i])
                         for i, t in enumerate(event)
                         if event.labels[i].decode('UTF-8') == 'UP'],
                       dtype=[('time', 'float'),
                              ('x_coords', 'int'),
                              ('y_coords', 'int')])
        ups = np.sort(ups, order=['time', 'x_coords', 'y_coords'])

        up_coords = []
        for frame_count, frame_time in enumerate(frame_times):
            # select indexes of up events during this frame
            idx = range(np.argmax(np.bitwise_not(ups['time'] < frame_time)),
                        np.argmax(ups['time'] > frame_time))
            frame_ups = np.array([(x,y) for x, y in zip(ups['x_coords'][idx],
                                                        ups['y_coords'][idx])])
            up_coords.append(frame_ups)
        return up_coords
    else:
        print(f"No {event_name} events found!")
        return None


def get_opticalflow(imagesequences, imgseq_name="Optical Flow"):
    imgseqs = [im for im in imagesequences if im.name == imgseq_name]
    if len(imgseqs):
        # Normalize?
        return imgseqs[0].as_array()
    else:
        return None

def stretch_to_framerate(t_start, t_stop, num_frames, frame_rate=None):
    if args.frame_rate is None:
        return np.arange(num_frames, dtype=int)
    else:
        new_num_frames = (imgseq.t_stop.rescale('s').magnitude
                        - imgseq.t_start.rescale('s').magnitude) \
                        * args.frame_rate
        return np.linspace(0, num_frames-1, new_num_frames).astype(int)

def plot_frame(frame, up_coords=None, cmap=plt.cm.gray, vmin=None, vmax=None,
               markersize=1):
    fig, ax = plt.subplots()
    img = ax.imshow(frame, interpolation='nearest',
                    cmap=cmap, vmin=vmin, vmax=vmax)
    plt.colorbar(img, ax=ax)

    ax.axis('image')
    ax.set_xticks([])
    ax.set_yticks([])
    # ax.set_xlim((0, dim_x))
    # ax.set_ylim((dim_y, 0))
    return ax

def plot_transitions(up_coords, markersize=1, ax=None):
    if up_coords.size:
        if ax is None:
            ax = plt.gca()
        ax.plot(up_coords[:,1], up_coords[:,0],
                marker='D', color='b', markersize=markersize, linestyle='None')
        # if len(pixels[0]) > 0.005*pixel_num:
        #     slope, intercept, _, _, stderr = scipy.stats.linregress(pixels[1], pixels[0])
        #     if stderr < 0.18:
        #         ax.plot(x, [intercept + slope*xi for xi in x], color='r')
    return ax

def plot_vectorfield(frame, skip_step=3, ax=None):
    # Every <skip_step> point in each direction.
    if ax is None:
        ax = plt.gca()
    dim_x, dim_y = frame.shape
    ax.quiver(np.arange(dim_y)[::skip_step],
              np.arange(dim_x)[::skip_step],
              np.real(frame[::skip_step,::skip_step]),
              -np.imag(frame[::skip_step,::skip_step]))
    return ax

if __name__ == '__main__':
    CLI = argparse.ArgumentParser()
    CLI.add_argument("--data",          nargs='?', type=str)
    CLI.add_argument("--frame_folder",  nargs='?', type=str)
    CLI.add_argument("--frame_name",    nargs='?', type=str)
    CLI.add_argument("--frame_format",  nargs='?', type=str)
    CLI.add_argument("--frame_rate",    nargs='?', type=none_or_float)
    CLI.add_argument("--colormap",      nargs='?', type=str)

    args = CLI.parse_args()

    blk = load_neo(args.data)
    blk = AnalogSignal2ImageSequence(blk)

    # get data
    imgseq = blk.segments[0].imagesequences[0]
    times = blk.segments[0].analogsignals[0].times  # to be replaced
    t_start = blk.segments[0].analogsignals[0].t_start  # to be replaced
    t_stop = blk.segments[0].analogsignals[0].t_stop  # to be replaced
    dim_t, dim_x, dim_y = imgseq.shape
    indices = np.where(np.isfinite(imgseq[0]))
    up_coords = get_events(blk.segments[0].events,
                           frame_times=times,
                           event_name='Transitions')
    optical_flow = get_opticalflow(blk.segments[0].imagesequences)

    # prepare plotting
    frame_idx = stretch_to_framerate(t_start=t_start,
                                     t_stop=t_stop,
                                     num_frames=dim_t,
                                     frame_rate=args.frame_rate)
    if args.colormap == 'gray':
        cmap = plt.cm.gray
    else:
        # 'gray', 'viridis' (sequential), 'coolwarm' (diverging), 'twilight' (cyclic)
        cmap = plt.get_cmap(args.colormap)

    frames = imgseq.as_array()
    vmin = np.nanmin(frames)
    vmax = np.nanmax(frames)
    markersize = 100 / max([dim_x, dim_y])

    # plot frames
    for i, frame_num in enumerate(frame_idx):
        ax = plot_frame(frames[frame_num], cmap=cmap, vmin=vmin, vmax=vmax)

        # if up_coords is not None:
        #     plot_transitions(up_coords[frame_num], markersize)
        if optical_flow is not None:
            plot_vectorfield(optical_flow[frame_num], skip_step=3)

        ax.set_ylabel('pixel size: {} '.format(imgseq.spatial_scale) \
                    + imgseq.spatial_scale.units.dimensionality.string)
        ax.set_xlabel('{:.3f} s'.format(times[frame_num].rescale('s')))

        save_plot(os.path.join(args.frame_folder,
                               args.frame_name + '_{}.{}'.format(str(i).zfill(5),
                               args.frame_format)))
        plt.close()