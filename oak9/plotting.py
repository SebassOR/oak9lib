"""Muestreo y graficado genéricos: no saben nada de sockets ni de
comandos concretos, solo llaman `read_fn()` (cualquier callable sin
argumentos que regrese un dict) a un intervalo fijo.
"""

import time


def sample(read_fn, duration=2.0, interval=0.05):
    """Llama `read_fn()` repetidamente por `duration` segundos.

    Regresa una lista de (segundos_transcurridos, dict_respuesta).
    """
    samples = []
    start = time.monotonic()
    while time.monotonic() - start < duration:
        elapsed = time.monotonic() - start
        samples.append((elapsed, read_fn()))
        time.sleep(interval)
    return samples


def plot(read_fn, fields, duration=2.0, interval=0.05):
    """Muestrea y grafica los campos numéricos indicados vs tiempo.

    >>> plot(lambda: robot.encoder.read(), ["left", "right"], duration=3)
    """
    import matplotlib.pyplot as plt

    if isinstance(fields, str):
        fields = [fields]

    samples = sample(read_fn, duration=duration, interval=interval)
    times = [t for t, _ in samples]

    fig, ax = plt.subplots()
    for field in fields:
        values = [response.get(field) for _, response in samples]
        ax.plot(times, values, label=field, marker=".")

    ax.set_xlabel("t (s)")
    ax.legend()
    ax.grid(True)
    plt.show()

    return samples


def live_plot(read_fn, fields, duration=None, interval=0.1, window=10.0):
    """Igual que `plot`, pero actualiza la gráfica en cada muestra.

    - duration=None: corre hasta que cierres la ventana o Ctrl+C.
    - window: segundos de historia visibles (ventana deslizante);
      None para mostrar todo desde el inicio.

    >>> live_plot(lambda: robot.encoder.read(), ["left", "right"])
    """
    import matplotlib.pyplot as plt

    if isinstance(fields, str):
        fields = [fields]

    plt.ion()
    fig, ax = plt.subplots()
    lines = {
        field: ax.plot([], [], label=field, marker=".")[0]
        for field in fields
    }
    ax.set_xlabel("t (s)")
    ax.legend()
    ax.grid(True)

    times = []
    series = {field: [] for field in fields}
    samples = []
    start = time.monotonic()

    try:
        while duration is None or (time.monotonic() - start) < duration:
            if not plt.fignum_exists(fig.number):
                break

            t = time.monotonic() - start
            response = read_fn()
            samples.append((t, response))

            times.append(t)
            for field in fields:
                series[field].append(response.get(field))

            if window is not None:
                cutoff = t - window
                while times and times[0] < cutoff:
                    times.pop(0)
                    for field in fields:
                        series[field].pop(0)

            for field in fields:
                lines[field].set_data(times, series[field])

            ax.relim()
            ax.autoscale_view()
            plt.pause(interval)

    except KeyboardInterrupt:
        pass

    return samples
