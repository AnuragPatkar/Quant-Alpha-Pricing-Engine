import cProfile
import pstats

def run_profile(fn, sort_by: str = "cumtime", top_n: int = 25):
    prof = cProfile.Profile()
    prof.enable()
    fn()
    prof.disable()
    stats = pstats.Stats(prof).sort_stats(sort_by)
    stats.print_stats(top_n)
