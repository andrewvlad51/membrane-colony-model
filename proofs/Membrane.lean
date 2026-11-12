/-
  Machine-checked statements for the paper
  "Independence by Access: A Colony Model of Separation of Duties
   in Autonomous AI Pipelines".

  Lean 4, core library only (no Mathlib).  Checked with Lean 4.35.0:   lean Membrane.lean
  The file contains no `sorry`.  The `#print axioms` lines at the end list what each
  theorem depends on.

  The development is over an arbitrary directed graph `E` on a vertex type `V`.
  In the paper `V` is the set of nodes, model-driven compartments and ports of a
  compartment system and `E` is its influence graph under either semantics.
-/

namespace Membrane

universe u v

/-! ## Paths that avoid the permitted mediators -/

section Graph

variable {V : Type u}

/-- `Reach E Y a b`: a path from `a` to `b` in `E` whose vertices after `a` all lie outside `Y`. -/
inductive Reach (E : V → V → Prop) (Y : V → Prop) (a : V) : V → Prop
  | refl : Reach E Y a a
  | step {b c : V} : Reach E Y a b → E b c → ¬ Y c → Reach E Y a c

/-- The blindness requirement `(c, X, Y)` fails: a forbidden source outside `Y` reaches `c`
    by a path that avoids `Y`. -/
def Violated (E : V → V → Prop) (X Y : V → Prop) (c : V) : Prop :=
  ∃ x, X x ∧ ¬ Y x ∧ Reach E Y x c

theorem Reach.trans {E : V → V → Prop} {Y : V → Prop} {a b c : V}
    (h₁ : Reach E Y a b) (h₂ : Reach E Y b c) : Reach E Y a c := by
  induction h₂ with
  | refl => exact h₁
  | step _ hbc hc ih => exact Reach.step ih hbc hc

/-- A path either is empty or starts with an edge. -/
theorem reach_head {E : V → V → Prop} {Y : V → Prop} {a c : V} (h : Reach E Y a c) :
    a = c ∨ ∃ n, E a n ∧ ¬ Y n ∧ Reach E Y n c := by
  induction h with
  | refl => exact Or.inl rfl
  | @step b c' _ hbc hc ih =>
    rcases ih with hab | ⟨n, han, hn, hnb⟩
    · subst hab
      exact Or.inr ⟨c', hbc, hc, Reach.refl⟩
    · exact Or.inr ⟨n, han, hn, Reach.step hnb hbc hc⟩

/-- Fewer edges and a larger avoid set give fewer paths. -/
theorem Reach.mono {E E' : V → V → Prop} {Y Y' : V → Prop}
    (hE : ∀ a b, E' a b → E a b) (hY : ∀ w, Y w → Y' w) {a b : V}
    (h : Reach E' Y' a b) : Reach E Y a b := by
  induction h with
  | refl => exact Reach.refl
  | step _ hbc hc ih => exact Reach.step ih (hE _ _ hbc) (fun hy => hc (hY _ hy))

/-- **Lemma 1, graph content for blindness.**  A requirement that holds in a graph holds in
    every subgraph.  Well-formedness makes the instruction graph a subgraph of the access
    graph. -/
theorem subgraph_requirement {E E' : V → V → Prop} (X Y : V → Prop) (c : V)
    (hE : ∀ a b, E' a b → E a b) (hreq : ¬ Violated E X Y c) : ¬ Violated E' X Y c := by
  intro hv
  obtain ⟨x, hX, hY, hr⟩ := hv
  exact hreq ⟨x, hX, hY, Reach.mono hE (fun _ h => h) hr⟩

/-! ## Theorem 1, label form: runs of the colony -/

/-- A marking: `μ v x` means that vertex `v` carries the mark of source `x`. -/
abbrev Marking (V : Type u) := V → V → Prop

/-- Initially every forbidden source outside `Y` carries its own mark. -/
abbrev init (X Y : V → Prop) : Marking V := fun w x => w = x ∧ X x ∧ ¬ Y x

/-- One step.  Along an edge `a → b` with `b` outside `Y`, the target acquires a set `T`
    of the marks of the source.  Any behaviour of a worker is some choice of `T`. -/
abbrev Step (E : V → V → Prop) (Y : V → Prop) (μ μ' : Marking V) : Prop :=
  ∃ a b, ∃ T : V → Prop, E a b ∧ ¬ Y b ∧ (∀ x, T x → μ a x) ∧
    μ' = fun w x => μ w x ∨ (w = b ∧ T x)

/-- A worst-case worker passes on every mark it holds. -/
abbrev WStep (E : V → V → Prop) (Y : V → Prop) (μ μ' : Marking V) : Prop :=
  ∃ a b, E a b ∧ ¬ Y b ∧ μ' = fun w x => μ w x ∨ (w = b ∧ μ a x)

inductive Run (S : Marking V → Marking V → Prop) (μ₀ : Marking V) : Marking V → Prop
  | start : Run S μ₀ μ₀
  | next {μ μ' : Marking V} : Run S μ₀ μ → S μ μ' → Run S μ₀ μ'

/-- Worst-case steps are steps. -/
theorem WStep.toStep {E : V → V → Prop} {Y : V → Prop} {μ μ' : Marking V}
    (h : WStep E Y μ μ') : Step E Y μ μ' := by
  obtain ⟨a, b, hab, hb, hμ⟩ := h
  exact ⟨a, b, μ a, hab, hb, fun _ hx => hx, hμ⟩

/-- Every mark has a path behind it. -/
theorem run_invariant (E : V → V → Prop) (X Y : V → Prop) {μ : Marking V}
    (h : Run (Step E Y) (init X Y) μ) :
    ∀ w x, μ w x → X x ∧ ¬ Y x ∧ Reach E Y x w := by
  induction h with
  | start =>
    intro w x hwx
    obtain ⟨hw, hX, hY⟩ := hwx
    subst hw
    exact ⟨hX, hY, Reach.refl⟩
  | next _ hstep ih =>
    obtain ⟨a, b, T, hab, hb, hT, hμ⟩ := hstep
    subst hμ
    intro w x hwx
    rcases hwx with h | ⟨hw, hTx⟩
    · exact ih w x h
    · subst hw
      obtain ⟨hX, hY, hr⟩ := ih a x (hT x hTx)
      exact ⟨hX, hY, Reach.step hr hab hb⟩

/-- **Theorem 1(a), soundness.**  If the requirement holds in the graph, the checker never
    carries a mark, whatever the workers do. -/
theorem soundness (E : V → V → Prop) (X Y : V → Prop) (c : V)
    (hreq : ¬ Violated E X Y c) {μ : Marking V} (h : Run (Step E Y) (init X Y) μ) :
    ∀ x, ¬ μ c x := by
  intro x hx
  obtain ⟨hX, hY, hr⟩ := run_invariant E X Y h c x hx
  exact hreq ⟨x, hX, hY, hr⟩

/-- **Theorem 1(b), completeness.**  If a forbidden source reaches the checker in the graph,
    some run with worst-case workers carries its mark to the checker. -/
theorem completeness (E : V → V → Prop) (X Y : V → Prop) (x c : V)
    (hX : X x) (hY : ¬ Y x) (h : Reach E Y x c) :
    ∃ μ, Run (WStep E Y) (init X Y) μ ∧ μ c x := by
  induction h with
  | refl => exact ⟨init X Y, Run.start, rfl, hX, hY⟩
  | @step b c' _ hbc hc ih =>
    obtain ⟨μ, hrun, hμ⟩ := ih
    exact ⟨fun w y => μ w y ∨ (w = c' ∧ μ b y), Run.next hrun ⟨b, c', hbc, hc, rfl⟩,
      Or.inr ⟨rfl, hμ⟩⟩

end Graph

/-! ## Theorem 1′, value form: noninterference through mediators -/

section Values

variable {V : Type u} {Val : Type v} [DecidableEq V]

/-- A scheduled action along one edge: the target's value becomes `g` of the source's value and
    its own old value.  `g` is arbitrary, as the behaviour of a model-driven worker is. -/
structure Act (V : Type u) (Val : Type v) where
  src : V
  tgt : V
  g : Val → Val → Val

def Act.apply (a : Act V Val) (σ : V → Val) : V → Val :=
  fun w => if w = a.tgt then a.g (σ a.src) (σ a.tgt) else σ w

def exec (σ : V → Val) : List (Act V Val) → V → Val
  | [] => σ
  | a :: as => exec (a.apply σ) as

/-- Every write into a mediator stores the same value in the two runs. -/
def MedAgree (Y : V → Prop) : (V → Val) → (V → Val) → List (Act V Val) → Prop
  | _, _, [] => True
  | σ₁, σ₂, a :: as =>
      (Y a.tgt → a.g (σ₁ a.src) (σ₁ a.tgt) = a.g (σ₂ a.src) (σ₂ a.tgt)) ∧
      MedAgree Y (a.apply σ₁) (a.apply σ₂) as

/-- The forbidden region: what the forbidden sources reach while avoiding the mediators. -/
def High (E : V → V → Prop) (X Y : V → Prop) (w : V) : Prop := Violated E X Y w

/-- **Theorem 1′.**  Two runs of one schedule that start equal outside the forbidden region,
    and in which the mediators receive the same values, stay equal outside that region. -/
theorem noninterference (E : V → V → Prop) (X Y : V → Prop) (sched : List (Act V Val)) :
    ∀ (σ₁ σ₂ : V → Val),
      (∀ a, a ∈ sched → E a.src a.tgt) →
      MedAgree Y σ₁ σ₂ sched →
      (∀ w, ¬ High E X Y w → σ₁ w = σ₂ w) →
      ∀ w, ¬ High E X Y w → exec σ₁ sched w = exec σ₂ sched w := by
  induction sched with
  | nil =>
    intro σ₁ σ₂ _ _ hag w hw
    exact hag w hw
  | cons a as ih =>
    intro σ₁ σ₂ hs hmed hag w hw
    have hm : (Y a.tgt → a.g (σ₁ a.src) (σ₁ a.tgt) = a.g (σ₂ a.src) (σ₂ a.tgt)) ∧
        MedAgree Y (a.apply σ₁) (a.apply σ₂) as := hmed
    have hedge : E a.src a.tgt := hs a (List.Mem.head as)
    have hone : ∀ z, ¬ High E X Y z → a.apply σ₁ z = a.apply σ₂ z := by
      intro z hz
      show (if z = a.tgt then a.g (σ₁ a.src) (σ₁ a.tgt) else σ₁ z)
         = (if z = a.tgt then a.g (σ₂ a.src) (σ₂ a.tgt) else σ₂ z)
      rcases Classical.em (z = a.tgt) with hzt | hzt
      · rw [ite_eq_left hzt, ite_eq_left hzt]
        rcases Classical.em (Y a.tgt) with hYt | hYt
        · exact hm.1 hYt
        · have htgt : ¬ High E X Y a.tgt := by
            intro h
            exact hz (hzt ▸ h)
          have hsrc : ¬ High E X Y a.src := by
            intro hsrc
            obtain ⟨x, hX, hYx, hr⟩ := hsrc
            exact htgt ⟨x, hX, hYx, Reach.step hr hedge hYt⟩
          rw [hag a.src hsrc, hag a.tgt htgt]
      · rw [ite_eq_right hzt, ite_eq_right hzt]
        exact hag z hz
    show exec (a.apply σ₁) as w = exec (a.apply σ₂) as w
    exact ih (a.apply σ₁) (a.apply σ₂) (fun b hb => hs b (List.Mem.tail a hb)) hm.2 hone w hw

end Values

/-! ## Theorem 2: admission of a new worker -/

section Spawn

variable {V : Type u}

/-- The graph extended by one new vertex `none`, with in-neighbours `I` and out-neighbours `O`. -/
def ext (E : V → V → Prop) (I O : V → Prop) : Option V → Option V → Prop
  | some a, some b => E a b
  | some a, none => I a
  | none, some b => O b
  | none, none => False

/-- A set of old vertices seen in the extended graph.  The new vertex is in no such set:
    it is not a forbidden source and not a mediator. -/
def liftP (P : V → Prop) : Option V → Prop
  | some a => P a
  | none => False

theorem reach_lift {E : V → V → Prop} {I O Y : V → Prop} {a b : V} (h : Reach E Y a b) :
    Reach (ext E I O) (liftP Y) (some a) (some b) := by
  induction h with
  | refl => exact Reach.refl
  | @step p q _ hpq hq ih =>
    have e : ext E I O (some p) (some q) := hpq
    have y : ¬ liftP Y (some q) := hq
    exact Reach.step ih e y

/-- What a path of the extended graph means in the old graph. -/
def Old (E : V → V → Prop) (Y I O : V → Prop) (x : V) : Option V → Prop
  | some w => Reach E Y x w ∨ ∃ a b, I a ∧ O b ∧ ¬ Y b ∧ Reach E Y x a ∧ Reach E Y b w
  | none => ∃ a, I a ∧ Reach E Y x a

theorem reach_ext {E : V → V → Prop} {Y I O : V → Prop} {x : V} {t : Option V}
    (h : Reach (ext E I O) (liftP Y) (some x) t) : Old E Y I O x t := by
  induction h with
  | refl =>
    show Reach E Y x x ∨ ∃ a b, I a ∧ O b ∧ ¬ Y b ∧ Reach E Y x a ∧ Reach E Y b x
    exact Or.inl Reach.refl
  | @step p q _ hpq hq ih =>
    cases p with
    | some b =>
      have ih' : Reach E Y x b ∨ ∃ a b', I a ∧ O b' ∧ ¬ Y b' ∧ Reach E Y x a ∧ Reach E Y b' b := ih
      cases q with
      | some c =>
        have e : E b c := hpq
        have y : ¬ Y c := hq
        show Reach E Y x c ∨ ∃ a b', I a ∧ O b' ∧ ¬ Y b' ∧ Reach E Y x a ∧ Reach E Y b' c
        rcases ih' with h | ⟨a, b', hI, hO, hYb, hxa, hbv⟩
        · exact Or.inl (Reach.step h e y)
        · exact Or.inr ⟨a, b', hI, hO, hYb, hxa, Reach.step hbv e y⟩
      | none =>
        have e : I b := hpq
        show ∃ a, I a ∧ Reach E Y x a
        rcases ih' with h | ⟨a, _, hI, _, _, hxa, _⟩
        · exact ⟨b, e, h⟩
        · exact ⟨a, hI, hxa⟩
    | none =>
      have ih' : ∃ a, I a ∧ Reach E Y x a := ih
      cases q with
      | some c =>
        have e : O c := hpq
        have y : ¬ Y c := hq
        show Reach E Y x c ∨ ∃ a b', I a ∧ O b' ∧ ¬ Y b' ∧ Reach E Y x a ∧ Reach E Y b' c
        obtain ⟨a, hI, hxa⟩ := ih'
        exact Or.inr ⟨a, c, hI, e, y, hxa, Reach.refl⟩
      | none =>
        have e : False := hpq
        exact e.elim

/-- **Theorem 2, admission.**  After a new vertex is added, the requirement fails exactly when
    it failed before, or the new vertex reads from the forward set and writes into the
    backward set (outside the mediators). -/
theorem spawn_admission (E : V → V → Prop) (X Y I O : V → Prop) (c : V) :
    Violated (ext E I O) (liftP X) (liftP Y) (some c) ↔
      Violated E X Y c ∨
      ∃ a b, I a ∧ O b ∧ ¬ Y b ∧ (∃ x, X x ∧ ¬ Y x ∧ Reach E Y x a) ∧ Reach E Y b c := by
  constructor
  · intro hv
    obtain ⟨s, hX, hY, hr⟩ := hv
    cases s with
    | none =>
      have e : False := hX
      exact e.elim
    | some x =>
      have hX' : X x := hX
      have hY' : ¬ Y x := hY
      have ho : Reach E Y x c ∨ ∃ a b, I a ∧ O b ∧ ¬ Y b ∧ Reach E Y x a ∧ Reach E Y b c :=
        reach_ext hr
      rcases ho with h | ⟨a, b, hI, hO, hYb, hxa, hbc⟩
      · exact Or.inl ⟨x, hX', hY', h⟩
      · exact Or.inr ⟨a, b, hI, hO, hYb, ⟨x, hX', hY', hxa⟩, hbc⟩
  · intro h
    rcases h with ⟨x, hX, hY, hr⟩ | ⟨a, b, hI, hO, hYb, ⟨x, hX, hY, hxa⟩, hbc⟩
    · have hX' : liftP X (some x) := hX
      have hY' : ¬ liftP Y (some x) := hY
      exact ⟨some x, hX', hY', reach_lift hr⟩
    · have hX' : liftP X (some x) := hX
      have hY' : ¬ liftP Y (some x) := hY
      have h1 : Reach (ext E I O) (liftP Y) (some x) (some a) := reach_lift hxa
      have e1 : ext E I O (some a) none := hI
      have y1 : ¬ liftP Y (none : Option V) := fun hf => hf
      have h2 : Reach (ext E I O) (liftP Y) (some x) none := Reach.step h1 e1 y1
      have e2 : ext E I O none (some b) := hO
      have y2 : ¬ liftP Y (some b) := hYb
      have h3 : Reach (ext E I O) (liftP Y) (some x) (some b) := Reach.step h2 e2 y2
      exact ⟨some x, hX', hY', Reach.trans h3 (reach_lift hbc)⟩

/-- **Corollary 2.3, role templates.**  A new vertex whose in-neighbours are in-neighbours of an
    existing vertex `m` and whose out-neighbours are out-neighbours of `m` breaks nothing. -/
theorem role_template (E : V → V → Prop) (X Y I O : V → Prop) (c m : V)
    (hm : ¬ Y m) (hI : ∀ a, I a → E a m) (hO : ∀ b, O b → E m b)
    (hreq : ¬ Violated E X Y c) :
    ¬ Violated (ext E I O) (liftP X) (liftP Y) (some c) := by
  intro h
  rcases (spawn_admission E X Y I O c).mp h with h | ⟨a, b, hIa, hOb, hYb, ⟨x, hX, hYx, hxa⟩, hbc⟩
  · exact hreq h
  · have h1 : Reach E Y x m := Reach.step hxa (hI a hIa) hm
    have h2 : Reach E Y x b := Reach.step h1 (hO b hOb) hYb
    exact hreq ⟨x, hX, hYx, Reach.trans h2 hbc⟩

end Spawn

/-! ## Theorem 3: control objects -/

section Control

variable {P : Type u}

/-- Events as seen from one control node.  `other` is any step of an untrusted compartment:
    by hypothesis (i) it has no rule on the node, so it cannot change it. -/
inductive Ev (P : Type u)
  | write (p : P)
  | remove (p : P)
  | effect (p : P)
  | other

/-- The state of the control node is the set of objects present.  The guarded effect for `p`
    is enabled only while the object for `p` is present (hypothesis (ii)). -/
def CStep (s : P → Prop) : Ev P → (P → Prop) → Prop
  | Ev.write p, s' => s' = fun q => s q ∨ q = p
  | Ev.remove p, s' => s' = fun q => s q ∧ q ≠ p
  | Ev.effect p, s' => s p ∧ s' = s
  | Ev.other, s' => s' = s

def Valid : (P → Prop) → List (Ev P) → Prop
  | _, [] => True
  | s, e :: es => ∃ s', CStep s e s' ∧ Valid s' es

/-- The object for `p` was written by a trusted compartment and not removed since. -/
def Before (done : List (Ev P)) (p : P) : Prop :=
  ∃ d₁ d₂, done = d₁ ++ Ev.write p :: d₂ ∧ ¬ (Ev.remove p ∈ d₂)

theorem before_snoc {done : List (Ev P)} {p : P} {e : Ev P}
    (h : Before done p) (he : e ≠ Ev.remove p) : Before (done ++ [e]) p := by
  obtain ⟨d₁, d₂, hd, hno⟩ := h
  subst hd
  refine ⟨d₁, d₂ ++ [e], by simp, ?_⟩
  intro hmem
  rcases List.mem_append.mp hmem with h | h
  · exact hno h
  · exact he (List.mem_singleton.mp h).symm

theorem before_write (done : List (Ev P)) (p : P) : Before (done ++ [Ev.write p]) p :=
  ⟨done, [], rfl, fun h => by cases h⟩

theorem control_aux :
    ∀ (pre done : List (Ev P)) (s : P → Prop) (post : List (Ev P)) (p : P),
      (∀ q, s q → Before done q) →
      Valid s (pre ++ Ev.effect p :: post) →
      Before (done ++ pre) p := by
  intro pre
  induction pre with
  | nil =>
    intro done s post p hinv hv
    have hv' : ∃ s', CStep s (Ev.effect p) s' ∧ Valid s' post := hv
    obtain ⟨s', hst, _⟩ := hv'
    have hst' : s p ∧ s' = s := hst
    have := hinv p hst'.1
    simpa using this
  | cons e pre ih =>
    intro done s post p hinv hv
    have hv' : ∃ s', CStep s e s' ∧ Valid s' (pre ++ Ev.effect p :: post) := hv
    obtain ⟨s', hstep, hrest⟩ := hv'
    have hinv' : ∀ q, s' q → Before (done ++ [e]) q := by
      intro q hq
      cases e with
      | write r =>
        have h2 : s' = fun q => s q ∨ q = r := hstep
        subst h2
        rcases hq with hq | hq
        · exact before_snoc (hinv q hq) (fun h => by cases h)
        · subst hq
          exact before_write done q
      | remove r =>
        have h2 : s' = fun q => s q ∧ q ≠ r := hstep
        subst h2
        obtain ⟨hq, hne⟩ := hq
        refine before_snoc (hinv q hq) ?_
        intro h
        cases h
        exact hne rfl
      | effect r =>
        have h2 : s r ∧ s' = s := hstep
        obtain ⟨_, h3⟩ := h2
        subst h3
        exact before_snoc (hinv q hq) (fun h => by cases h)
      | other =>
        have h2 : s' = s := hstep
        subst h2
        exact before_snoc (hinv q hq) (fun h => by cases h)
    have := ih (done ++ [e]) s' post p hinv' hrest
    simpa [List.append_assoc] using this

/-- **Theorem 3, control objects.**  In a run that starts with an empty control node, every
    guarded effect is preceded by a trusted write of its object, with no removal in between. -/
theorem control_object (pre post : List (Ev P)) (p : P)
    (h : Valid (fun _ => False) (pre ++ Ev.effect p :: post)) :
    ∃ pre₁ pre₂, pre = pre₁ ++ Ev.write p :: pre₂ ∧ ¬ (Ev.remove p ∈ pre₂) := by
  have := control_aux pre [] (fun _ => False) post p (fun _ hq => hq.elim) h
  simpa [Before] using this

end Control

/-! ## Theorem 4: delimiter integrity -/

section Render

variable {α : Type u}

structure Field (α : Type u) where
  trusted : Bool
  text : List α

/-- One rendered segment, each symbol tagged with whether a trusted field contributed it.
    Trusted fields are copied.  Untrusted fields pass the encoding. -/
def seg (enc : List α → List α) (f : Field α) : List (α × Bool) :=
  match f.trusted with
  | true => f.text.map (fun a => (a, true))
  | false => (enc f.text).map (fun a => (a, false))

def render (enc : List α → List α) : List (Field α) → List (α × Bool)
  | [] => []
  | f :: fs => seg enc f ++ render enc fs

theorem seg_integrity (enc : List α → List α) (r : α) (henc : ∀ t, ¬ (r ∈ enc t))
    (f : Field α) : ∀ p, p ∈ seg enc f → p.1 = r → p.2 = true := by
  intro p hp hr
  cases f with
  | mk tr txt =>
    cases tr with
    | true =>
      have hp' : p ∈ txt.map (fun a => (a, true)) := hp
      obtain ⟨a, _, ha⟩ := List.mem_map.mp hp'
      subst ha
      rfl
    | false =>
      have hp' : p ∈ (enc txt).map (fun a => (a, false)) := hp
      obtain ⟨a, hmem, ha⟩ := List.mem_map.mp hp'
      subst ha
      have hr' : a = r := hr
      subst hr'
      exact absurd hmem (henc txt)

/-- **Theorem 4, delimiter integrity.**  If the encoding never produces the reserved symbol,
    every reserved symbol in the rendered text was contributed by a trusted field. -/
theorem delimiter_integrity (enc : List α → List α) (r : α) (henc : ∀ t, ¬ (r ∈ enc t))
    (fs : List (Field α)) : ∀ p, p ∈ render enc fs → p.1 = r → p.2 = true := by
  induction fs with
  | nil =>
    intro p hp
    cases hp
  | cons f fs ih =>
    intro p hp hr
    have hp' : p ∈ seg enc f ++ render enc fs := hp
    rcases List.mem_append.mp hp' with h | h
    · exact seg_integrity enc r henc f p h hr
    · exact ih p h hr

end Render

/-! ## Theorem 5: identity, graph content -/

section Identity

variable {V : Type u}

/-- **Theorem 5(a).**  If every node in which the objects of `f` can land is one from which the
    checker cannot be reached, `f` cannot influence the checker. -/
theorem identity_by_environment (E : V → V → Prop) (Y : V → Prop) (f c : V) (hfc : f ≠ c)
    (hland : ∀ n, E f n → ¬ Y n → ¬ Reach E Y n c) :
    ¬ Violated E (fun w => w = f) Y c := by
  intro hv
  obtain ⟨x, hx, _, hr⟩ := hv
  have hx' : x = f := hx
  subst hx'
  rcases reach_head hr with h | ⟨n, hfn, hn, hnc⟩
  · exact hfc h
  · exact hland n hfn hn hnc

/-- **Theorem 5(b), graph content.**  If `f` can place an object in a node from which the
    checker is reachable, the requirement fails.  That classification by content lets every
    writer reach such a node is the modelling step stated in the paper. -/
theorem identity_by_content (E : V → V → Prop) (Y : V → Prop) (f n c : V)
    (hf : ¬ Y f) (hfn : E f n) (hn : ¬ Y n) (hnc : Reach E Y n c) :
    Violated E (fun w => w = f) Y c :=
  ⟨f, rfl, hf, Reach.trans (Reach.step Reach.refl hfn hn) hnc⟩

/-- **Theorem 5(a), run form.**  No run carries a mark of `f` to the checker, whatever `f`
    writes. -/
theorem identity_by_environment_runs (E : V → V → Prop) (Y : V → Prop) (f c : V) (hfc : f ≠ c)
    (hland : ∀ n, E f n → ¬ Y n → ¬ Reach E Y n c)
    {μ : Marking V} (h : Run (Step E Y) (init (fun w => w = f) Y) μ) : ∀ x, ¬ μ c x :=
  soundness E (fun w => w = f) Y c (identity_by_environment E Y f c hfc hland) h

/-- **Theorem 5(b), run form.**  Some run with worst-case workers carries the mark of `f` to
    the checker. -/
theorem identity_by_content_run (E : V → V → Prop) (Y : V → Prop) (f n c : V)
    (hf : ¬ Y f) (hfn : E f n) (hn : ¬ Y n) (hnc : Reach E Y n c) :
    ∃ μ, Run (WStep E Y) (init (fun w => w = f) Y) μ ∧ μ c f :=
  completeness E (fun w => w = f) Y f c rfl hf (Reach.trans (Reach.step Reach.refl hfn hn) hnc)

end Identity

/-! ## Theorem 6: composition -/

section Composition

variable {V : Type u}

/-- Lemma for Theorem 6(a).  From a caller vertex outside the interface, a path that avoids
    the interface never leaves the caller. -/
theorem composition (E₁ E₂ : V → V → Prop) (V₁ V₂ J A : V → Prop)
    (h₁ : ∀ a b, E₁ a b → V₁ a ∧ V₁ b) (h₂ : ∀ a b, E₂ a b → V₂ a ∧ V₂ b)
    (hJ : ∀ w, V₁ w → V₂ w → J w) (hA : ∀ w, J w → A w)
    {a b : V} (ha : V₁ a) (haJ : ¬ J a)
    (h : Reach (fun x y => E₁ x y ∨ E₂ x y) A a b) : V₁ b ∧ ¬ J b := by
  induction h with
  | refl => exact ⟨ha, haJ⟩
  | @step p q _ hpq hq ih =>
    obtain ⟨hp1, hpJ⟩ := ih
    rcases hpq with h | h
    · exact ⟨(h₁ p q h).2, fun hj => hq (hA q hj)⟩
    · exact absurd (hJ p hp1 (h₂ p q h).1) hpJ

/-- From a callee vertex outside the interface, a path that avoids the interface is a path of
    the callee alone. -/
theorem callee_side (E₁ E₂ : V → V → Prop) (V₁ V₂ J Y : V → Prop)
    (h₁ : ∀ a b, E₁ a b → V₁ a ∧ V₁ b) (h₂ : ∀ a b, E₂ a b → V₂ a ∧ V₂ b)
    (hJ : ∀ w, V₁ w → V₂ w → J w)
    {a b : V} (ha : V₂ a) (haJ : ¬ J a)
    (h : Reach (fun x y => E₁ x y ∨ E₂ x y) (fun w => Y w ∨ J w) a b) :
    Reach E₂ Y a b ∧ V₂ b ∧ ¬ J b := by
  induction h with
  | refl => exact ⟨Reach.refl, ha, haJ⟩
  | @step p q _ hpq hq ih =>
    obtain ⟨hr, hp2, hpJ⟩ := ih
    rcases hpq with h | h
    · exact absurd (hJ p (h₁ p q h).1 hp2) hpJ
    · exact ⟨Reach.step hr h (fun hy => hq (Or.inl hy)), (h₂ p q h).2, fun hj => hq (Or.inr hj)⟩

/-- **Theorem 6(a).**  No path that avoids the interface joins a caller vertex outside the
    interface and a callee vertex outside it, in either direction. -/
theorem interface_separation (E₁ E₂ : V → V → Prop) (V₁ V₂ J : V → Prop)
    (h₁ : ∀ a b, E₁ a b → V₁ a ∧ V₁ b) (h₂ : ∀ a b, E₂ a b → V₂ a ∧ V₂ b)
    (hJ : ∀ w, V₁ w → V₂ w → J w)
    {a b : V} (ha : V₁ a) (haJ : ¬ J a) (hb : V₂ b) (hbJ : ¬ J b) :
    ¬ Reach (fun x y => E₁ x y ∨ E₂ x y) J a b ∧
    ¬ Reach (fun x y => E₁ x y ∨ E₂ x y) J b a := by
  constructor
  · intro h
    have hres := composition E₁ E₂ V₁ V₂ J J h₁ h₂ hJ (fun _ hj => hj) ha haJ h
    exact hres.2 (hJ b hres.1 hb)
  · intro h
    have h' : Reach (fun x y => E₁ x y ∨ E₂ x y) (fun w => False ∨ J w) b a :=
      Reach.mono (fun _ _ e => e) (fun _ hw => hw.elim False.elim id) h
    have hres := callee_side E₁ E₂ V₁ V₂ J (fun _ => False) h₁ h₂ hJ hb hbJ h'
    exact hres.2.2 (hJ a ha hres.2.1)

/-- **Theorem 6(b).**  A callee node outside the caller has the same writers after composition. -/
theorem composition_writers (E₁ E₂ : V → V → Prop) (V₁ : V → Prop)
    (h₁ : ∀ a b, E₁ a b → V₁ a ∧ V₁ b) (n : V) (hn : ¬ V₁ n) (m : V) :
    (E₁ m n ∨ E₂ m n) ↔ E₂ m n :=
  ⟨fun h => h.elim (fun h => absurd (h₁ m n h).2 hn) id, Or.inr⟩

/-- **Theorem 6(c).**  A requirement of the callee holds in the composition with the caller's
    vertices added to the sources and the interface added to the mediators. -/
theorem composition_requirement (E₁ E₂ : V → V → Prop) (V₁ V₂ J X Y : V → Prop)
    (h₁ : ∀ a b, E₁ a b → V₁ a ∧ V₁ b) (h₂ : ∀ a b, E₂ a b → V₂ a ∧ V₂ b)
    (hJ : ∀ w, V₁ w → V₂ w → J w)
    (c : V) (hX : ∀ x, X x → V₂ x) (hc : ¬ V₁ c)
    (hreq : ¬ Violated E₂ X Y c) :
    ¬ Violated (fun x y => E₁ x y ∨ E₂ x y) (fun w => X w ∨ (V₁ w ∧ ¬ J w))
        (fun w => Y w ∨ J w) c := by
  intro hv
  obtain ⟨x, hx, hxY, hr⟩ := hv
  rcases hx with hx | ⟨hx1, hxJ⟩
  · have hxJ : ¬ J x := fun hj => hxY (Or.inr hj)
    obtain ⟨hr2, _, _⟩ := callee_side E₁ E₂ V₁ V₂ J Y h₁ h₂ hJ (hX x hx) hxJ hr
    exact hreq ⟨x, hx, fun hy => hxY (Or.inl hy), hr2⟩
  · exact hc (composition E₁ E₂ V₁ V₂ J (fun w => Y w ∨ J w) h₁ h₂ hJ (fun _ hj => Or.inr hj)
      hx1 hxJ hr).1

end Composition

end Membrane

#print axioms Membrane.subgraph_requirement
#print axioms Membrane.soundness
#print axioms Membrane.completeness
#print axioms Membrane.noninterference
#print axioms Membrane.spawn_admission
#print axioms Membrane.role_template
#print axioms Membrane.control_object
#print axioms Membrane.delimiter_integrity
#print axioms Membrane.identity_by_environment
#print axioms Membrane.identity_by_environment_runs
#print axioms Membrane.identity_by_content
#print axioms Membrane.identity_by_content_run
#print axioms Membrane.composition
#print axioms Membrane.interface_separation
#print axioms Membrane.composition_writers
#print axioms Membrane.composition_requirement
