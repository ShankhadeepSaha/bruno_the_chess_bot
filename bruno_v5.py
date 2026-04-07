import chess
import time
import random

#================= Evaluating the board =======================================================
PIECE_VALUES = {
    chess.PAWN:   100,
    chess.KNIGHT: 600,
    chess.BISHOP: 610,
    chess.ROOK:   1000,
    chess.QUEEN:  2000,
    chess.KING:   20000
}

PAWN_TABLE = [
     0,   0,   0,   0,   0,   0,   0,   0,
    50,  50,  50,  50,  50,  50,  50,  50,
    10,  10,  20,  30,  30,  20,  10,  10,
     5,   5,  10,  25,  25,  10,   5,   5,
     0,   0,   0,  20,  20,   0,   0,   0,
     5,  -5, -10,   0,   0, -10,  -5,   5,
     5,  10,  10, -20, -20,  10,  10,   5,
     0,   0,   0,   0,   0,   0,   0,   0
]

KNIGHT_TABLE = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20,   0,   0,   0,   0, -20, -40,
    -30,   0,  10,  15,  15,  10,   0, -30,
    -30,   5,  15,  20,  20,  15,   5, -30,
    -30,   0,  15,  20,  20,  15,   0, -30,
    -30,   5,  10,  15,  15,  10,   5, -30,
    -40, -20,   0,   5,   5,   0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50
]

BISHOP_TABLE = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,  10,  10,   5,   0, -10,
    -10,   5,   5,  10,  10,   5,   5, -10,
    -10,   0,  10,  10,  10,  10,   0, -10,
    -10,  10,  10,  10,  10,  10,  10, -10,
    -10,   5,   0,   0,   0,   0,   5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20
]

ROOK_TABLE = [
     0,   0,   0,   0,   0,   0,   0,   0,
     5,  10,  10,  10,  10,  10,  10,   5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
     0,   0,   0,   5,   5,   0,   0,   0
]

QUEEN_TABLE = [
    -20, -10, -10,  -5,  -5, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,   5,   5,   5,   0, -10,
     -5,   0,   5,   5,   5,   5,   0,  -5,
      0,   0,   5,   5,   5,   5,   0,  -5,
    -10,   5,   5,   5,   5,   5,   0, -10,
    -10,   0,   5,   0,   0,   0,   0, -10,
    -20, -10, -10,  -5,  -5, -10, -10, -20
]

KING_MIDDLEGAME_TABLE = [
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
     20,  20,   0,   0,   0,   0,  20,  20,
     20,  30,  10,   0,   0,  10,  30,  20
]

PIECE_TABLES = {
    chess.PAWN:   PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK:   ROOK_TABLE,
    chess.QUEEN:  QUEEN_TABLE,
    chess.KING:   KING_MIDDLEGAME_TABLE
}

def get_piece_square_score(piece_type, square, is_white):
    table = PIECE_TABLES[piece_type]
    if is_white:
        index = (7 - chess.square_rank(square)) * 8 + chess.square_file(square)
    else:
        index = chess.square_rank(square) * 8 + chess.square_file(square)
    return table[index]

def evaluate_board(board):
    if board.is_checkmate():
        return -99999 if board.turn == chess.WHITE else 99999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0

    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue
        value  = PIECE_VALUES[piece.piece_type]
        pstval = get_piece_square_score(piece.piece_type, square, piece.color == chess.WHITE)
        if piece.color == chess.WHITE:
            score += value + pstval
        else:
            score -= value + pstval

    mobility_weight = 10
    white_mobility  = len(list(board.legal_moves)) if board.turn == chess.WHITE else 0
    black_mobility  = len(list(board.legal_moves)) if board.turn == chess.BLACK else 0
    score += mobility_weight * (white_mobility - black_mobility)

    return score

#=================================================================================================
# SEE — Static Exchange Evaluation
# Returns the material gain/loss from a capture sequence on `square`,
# starting with `move` being played. Positive = winning capture, negative = losing.
#=================================================================================================
def see(board, move):
    """
    Static Exchange Evaluation.

    Simulates the full recapture sequence on the target square without
    pushing any moves onto the board. Returns the net material swing
    from the perspective of the side making `move`.

    Algorithm (Swap algorithm):
      gain[0] = value of the piece being captured
      Then alternate sides: each side captures with its least-valuable
      attacker currently on the square. The gain array records what each
      side *could* gain if they stopped capturing at that point.
      Finally, fold the array back: a side will only recapture if it
      improves their result (they can always choose NOT to recapture).
    """
    to_sq   = move.to_square
    from_sq = move.from_square

    # Value of the piece on the target square (what we capture first)
    target_piece = board.piece_at(to_sq)
    if target_piece is None:
        # En-passant: captured pawn is not on to_sq
        if board.is_en_passant(move):
            gain = [PIECE_VALUES[chess.PAWN]]
        else:
            return 0
    else:
        gain = [PIECE_VALUES[target_piece.piece_type]]

    # Build a mutable occupancy bitboard so we can remove pieces as they
    # are used in the exchange without touching the real board.
    occupancy = board.occupied

    # The moving piece is the first attacker; record its value for the
    # next iteration (the opponent will capture *it*).
    moving_piece = board.piece_at(from_sq)
    if moving_piece is None:
        return 0
    last_attacker_value = PIECE_VALUES[moving_piece.piece_type]

    # Remove the moving piece from the occupancy mask (it has "moved" to to_sq).
    occupancy ^= chess.BB_SQUARES[from_sq]

    # Alternate sides, each time finding the cheapest remaining attacker.
    side_to_move = not board.turn   # after our move, opponent recaptures

    depth = 1
    while True:
        # Find all pieces of `side_to_move` that attack `to_sq`
        # given the current occupancy (some pieces may be x-ray blocked).
        attackers = _get_attackers(board, to_sq, side_to_move, occupancy)
        if not attackers:
            break   # no recapture available → stop

        # Pick the least-valuable attacker (LVA)
        lva_sq, lva_value = _least_valuable_attacker(board, attackers)

        # Record the gain at this depth: capturing `last_attacker_value`
        gain.append(last_attacker_value - gain[depth - 1])

        last_attacker_value = lva_value

        # Remove this attacker from occupancy
        occupancy ^= chess.BB_SQUARES[lva_sq]

        side_to_move = not side_to_move
        depth += 1

    # Fold back: each side only recaptures if it improves their score.
    # Walk gain[] from the end, keeping the maximum.
    while depth > 1:
        depth -= 1
        gain[depth - 1] = max(-gain[depth], gain[depth - 1])

    return gain[0]


def _get_attackers(board, square, color, occupancy):
    """
    Return a bitboard of `color` pieces that attack `square`,
    respecting the given `occupancy` mask (for sliding pieces).
    Uses python-chess's built-in attacker masks filtered by occupancy.
    """
    attackers_bb = chess.SquareSet()

    # Non-sliding: pawns, knights, king
    color_bb = board.occupied_co[color]

    # Pawn attacks: a pawn of `color` attacks `square` if a pawn of
    # `color` sits on a square that would attack `square`.
    pawn_attacks = chess.BB_PAWN_ATTACKS[not color][square]   # squares a pawn on `square` sees for opponent
    pawns = board.pawns & color_bb & pawn_attacks & occupancy
    attackers_bb |= chess.SquareSet(pawns)

    # Knight
    knight_attacks = chess.BB_KNIGHT_ATTACKS[square]
    knights = board.knights & color_bb & knight_attacks & occupancy
    attackers_bb |= chess.SquareSet(knights)

    # King
    king_attacks = chess.BB_KING_ATTACKS[square]
    kings = board.kings & color_bb & king_attacks & occupancy
    attackers_bb |= chess.SquareSet(kings)

    # Sliding: bishops/queens (diagonal)
    diag_attackers = chess.BB_DIAG_ATTACKS[square][chess.BB_DIAG_MASKS[square] & occupancy]
    bishops_queens = (board.bishops | board.queens) & color_bb & diag_attackers & occupancy
    attackers_bb |= chess.SquareSet(bishops_queens)

    # Sliding: rooks/queens (rank & file)
    rank_attackers = chess.BB_RANK_ATTACKS[square][chess.BB_RANK_MASKS[square] & occupancy]
    file_attackers = chess.BB_FILE_ATTACKS[square][chess.BB_FILE_MASKS[square] & occupancy]
    rooks_queens = (board.rooks | board.queens) & color_bb & (rank_attackers | file_attackers) & occupancy
    attackers_bb |= chess.SquareSet(rooks_queens)

    return attackers_bb


def _least_valuable_attacker(board, attackers_bb):
    """
    Given a SquareSet of attackers, return (square, piece_value) of
    the least-valuable piece in that set.
    """
    best_sq    = None
    best_value = float('inf')
    for sq in attackers_bb:
        piece = board.piece_at(sq)
        if piece is None:
            continue
        v = PIECE_VALUES[piece.piece_type]
        if v < best_value:
            best_value = v
            best_sq    = sq
    return best_sq, best_value


#=================================================================================================
# Zobrist hash table — precomputed once at startup
ZOBRIST_TABLE = {
    (piece_type, color, square): random.getrandbits(64)
    for piece_type in chess.PIECE_TYPES
    for color in [True, False]
    for square in chess.SQUARES
}
ZOBRIST_TURN = random.getrandbits(64)

transposition_table = {}


def zobrist_hash(board):
    h = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            h ^= ZOBRIST_TABLE[(piece.piece_type, piece.color, square)]
    if board.turn == chess.WHITE:
        h ^= ZOBRIST_TURN
    return h


#=================================================================================================
# Move ordering — four buckets (SEE-aware)
#   Bucket 0: good captures  (SEE >= 0)
#   Bucket 1: checks         (quiet moves that give check)
#   Bucket 2: quiet moves
#   Bucket 3: bad captures   (SEE < 0)
#=================================================================================================
def order_moves(board):
    good_captures = []
    checks        = []
    quiet         = []
    bad_captures  = []

    for move in board.legal_moves:
        if board.is_capture(move):
            score = see(board, move)
            if score >= 0:
                good_captures.append((move, score))
            else:
                bad_captures.append((move, score))
        else:
            board.push(move)
            if board.is_check():
                checks.append(move)
            else:
                quiet.append(move)
            board.pop()

    # Sort good captures descending by SEE gain, bad captures ascending (least losing first)
    good_captures.sort(key=lambda x: x[1], reverse=True)
    bad_captures.sort(key=lambda x: x[1], reverse=True)

    return (
        [m for m, _ in good_captures]
        + checks
        + quiet
        + [m for m, _ in bad_captures]
    )


#=================================================================================================
# Quiescence Search
# Called at depth == 0 instead of returning evaluate_board directly.
# Mirrors the plain min/max style of minimax — no negamax sign flipping.
# Searches only SEE >= 0 captures until the position is "quiet",
# eliminating the horizon effect where Bruno blunders into exchanges
# right at the edge of its main search.
#=================================================================================================
def quiescence(board, is_maximizing, alpha, beta):
    """
    Stand-pat: evaluate the current position. A side can always choose
    to stop capturing, so the static eval is a lower bound (for the
    maximiser) or upper bound (for the minimiser).
    Then try all SEE >= 0 captures and recurse, matching the min/max
    convention of minimax() so scores are always in the same frame.
    """
    stand_pat = evaluate_board(board)

    if board.is_game_over():
        return stand_pat

    if is_maximizing:
        if stand_pat >= beta:
            return beta             # beta cut-off — opponent won't allow this
        alpha = max(alpha, stand_pat)

        for move in board.legal_moves:
            if not board.is_capture(move):
                continue
            if see(board, move) < 0:
                continue            # skip losing captures

            board.push(move)
            score = quiescence(board, False, alpha, beta)
            board.pop()

            if score >= beta:
                return beta
            alpha = max(alpha, score)

        return alpha

    else:
        if stand_pat <= alpha:
            return alpha            # alpha cut-off
        beta = min(beta, stand_pat)

        for move in board.legal_moves:
            if not board.is_capture(move):
                continue
            if see(board, move) < 0:
                continue

            board.push(move)
            score = quiescence(board, True, alpha, beta)
            board.pop()

            if score <= alpha:
                return alpha
            beta = min(beta, score)

        return beta


#=================================================================================================
# Minimax with Alpha-Beta + Quiescence at leaf nodes
#=================================================================================================
def minimax(board, depth, is_maximizing, alpha=float('-inf'), beta=float('inf')):
    key = (zobrist_hash(board), depth, is_maximizing)
    if key in transposition_table:
        return transposition_table[key]

    if board.is_game_over():
        score = evaluate_board(board)
        transposition_table[key] = score
        return score

    # At depth == 0, hand off to quiescence instead of raw evaluation.
    # Same min/max convention — no sign flipping needed.
    if depth == 0:
        score = quiescence(board, is_maximizing, alpha, beta)
        transposition_table[key] = score
        return score

    if is_maximizing:
        best = float('-inf')
        for move in order_moves(board):
            board.push(move)
            score = minimax(board, depth - 1, False, alpha, beta)
            board.pop()
            best  = max(best, score)
            alpha = max(alpha, best)
            if beta <= alpha:
                break
    else:
        best = float('inf')
        for move in order_moves(board):
            board.push(move)
            score = minimax(board, depth - 1, True, alpha, beta)
            board.pop()
            best = min(best, score)
            beta = min(beta, best)
            if beta <= alpha:
                break

    transposition_table[key] = best
    return best


def get_bruno_move(board, depth):
    transposition_table.clear()    # fresh table for each of Bruno's turns
    best_score = float('inf')
    best_move  = None
    for move in order_moves(board):
        board.push(move)
        score = minimax(board, depth - 1, True, float('-inf'), float('inf'))
        board.pop()
        if score < best_score:
            best_score = score
            best_move  = move
    return best_move


# =============================================================================
# MAIN GAME LOOP
# =============================================================================
def main():
    board = chess.Board()
    depth = 4

    print("\n=====================================================================")
    print("================== Welcome to Chess with Bruno ======================")
    print("=====================================================================")
    print("         You are playing as WHITE. Bruno is playing as BLACK.      \n")
    print("============== Commands: 'q' to Quit  |  'u' to Undo ===============")
    print("=====================================================================")

    while not board.is_game_over():

        if board.turn == chess.WHITE:
            raw_input = input("\nYour move (White): ").strip()
            cmd = raw_input.lower()

            if cmd == 'q':
                print("Game ended. Bruno wins by abandonment!")
                return

            if cmd == 'u':
                if len(board.move_stack) >= 2:
                    board.pop()
                    board.pop()
                    print("Moves undone.")
                else:
                    print("Cannot undo — not enough moves in history!")
                continue

            try:
                board.push(board.parse_san(raw_input))
            except ValueError:
                try:
                    board.push(board.parse_uci(raw_input))
                except ValueError:
                    print("\n Invalid move. Try again.")
                    continue

        else:
            start = time.time()
            bruno_move = get_bruno_move(board, depth)
            elapsed = time.time() - start

            if bruno_move:
                print(f"Bruno plays (Black): {board.san(bruno_move)}")
                print(f"Time taken: {elapsed:.2f} seconds")
                board.push(bruno_move)

    print("\n--- Game Over ---")
    print(f"Result: {board.result()}")


if __name__ == "__main__":
    main()