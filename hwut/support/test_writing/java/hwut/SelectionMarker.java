/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: REMEMBERS WHICH CANDIDATE OBJECTS HAVE BEEN CHOSEN at one selection
 *          site -- the port of 'SelectionMarker' in
 *          'python/deterministic_random.py'; used by
 *          'DeterministicStream.selectUnchosen'.
 *
 * Keyed by object IDENTITY ('=='), never 'equals': two equal candidates are
 * still distinct alternatives. The marker is the caller's, so 'prefer
 * unchosen' is reproducible whatever container holds the candidates -- the
 * marker, not the container, is the memory. One marker per logical site.
 * _____________________________________________________________________________
 */
package hwut;

import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.Set;

public final class SelectionMarker {
    final Set<Object> chosen = Collections.newSetFromMap(new IdentityHashMap<>());

    /** RETURN: SelectionMarker, with nothing chosen. */
    public SelectionMarker() {}

    /** RETURN: nothing; every chosen candidate is forgotten, the next cycle
     *          restarts. */
    public void reset() { chosen.clear(); }
}
