import chess
import chess.pgn
import sys
import os
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from stockfish import Stockfish
from bruno_v5 import get_bruno_move

# ── Settings ──────────────────────────────────────────────────────────────────
STOCKFISH_PATH = os.path.join(BASE_DIR, "stockfish.exe")
STOCKFISH_ELO  = 1600
BRUNO_DEPTH    = 3
ROUNDS         = 10
PGN_DIR        = os.path.join(BASE_DIR, "pgn_games")   # one .pgn per game saved here
# ──────────────────────────────────────────────────────────────────────────────


def play_one_game(game_number):
    board    = chess.Board()
    pgn_game = chess.pgn.Game()
    pgn_game.headers["Event"]  = "Bruno vs Stockfish"
    pgn_game.headers["Site"]   = "Local Machine"
    pgn_game.headers["Date"]   = datetime.datetime.now().strftime("%Y.%m.%d")
    pgn_game.headers["Round"]  = str(game_number)
    pgn_game.headers["White"]  = f"Stockfish (ELO {STOCKFISH_ELO})"
    pgn_game.headers["Black"]  = "Bruno"
    pgn_node = pgn_game

    sf = Stockfish(path=STOCKFISH_PATH,
                   parameters={"UCI_LimitStrength": True, "UCI_Elo": STOCKFISH_ELO})

    print(f"\n{'='*50}")
    print(f"Game {game_number} | Bruno=Black | Stockfish ELO={STOCKFISH_ELO}")
    print(f"{'='*50}")

    while not board.is_game_over():
        is_bruno = board.turn == chess.BLACK

        if is_bruno:
            move = get_bruno_move(board, BRUNO_DEPTH)
            if move is None:
                print("  Bruno returned no move — picking first legal move as fallback")
                move = next(iter(board.legal_moves))
        else:
            sf.set_fen_position(board.fen())
            move = chess.Move.from_uci(sf.get_best_move())

        print(f"  {'Bruno     ' if is_bruno else 'Stockfish '}: {board.san(move)}")
        pgn_node = pgn_node.add_main_variation(move)
        board.push(move)

    result = board.result()
    pgn_game.headers["Result"] = result
    print(f"  Result: {result}")

    # Save to its own file: pgn_games/game_01.pgn, game_02.pgn, …
    os.makedirs(PGN_DIR, exist_ok=True)
    pgn_path = os.path.join(PGN_DIR, f"game_{game_number:02d}.pgn")
    with open(pgn_path, "w") as f:
        print(pgn_game, file=f)
    print(f"  Saved → {pgn_path}")

    if result == "0-1":   return "win"
    elif result == "1-0": return "loss"
    else:                 return "draw"


def run_match():
    wins, losses, draws = 0, 0, 0

    for i in range(ROUNDS):
        outcome = play_one_game(i + 1)

        if outcome == "win":    wins   += 1
        elif outcome == "loss": losses += 1
        else:                   draws  += 1

        print(f"  Score so far → Bruno W:{wins} L:{losses} D:{draws}")

    total = wins + losses + draws
    pct   = (wins + 0.5 * draws) / total * 100

    print(f"\n{'='*50}")
    print(f"Match complete: Bruno vs Stockfish (ELO {STOCKFISH_ELO})")
    print(f"Wins: {wins} | Losses: {losses} | Draws: {draws}")
    print(f"Bruno's score: {pct:.1f}%")
    print(f"PGN files saved in: {PGN_DIR}/")
    print(f"{'='*50}")


if __name__ == "__main__":
    run_match()