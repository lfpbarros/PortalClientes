// Lightweight per-column table filtering for all tables
// Usage: automatically applies to all <table> elements on the page.
// Opt-out by adding data-filter="off" or class "no-filter" on the table.

(function () {
  function textOf(node) {
    return (node?.textContent || "").trim().toLowerCase();
  }

  function buildFilterRow(table) {
    if (!table.tHead || !table.tHead.rows.length) return null;
    var headerRow = table.tHead.rows[0];
    var filterRow = document.createElement('tr');
    filterRow.className = 'table-filters-row';

    var colCount = headerRow.cells.length;
    for (var i = 0; i < colCount; i++) {
      var th = document.createElement('th');
      var headerCell = headerRow.cells[i];
      var headerLabel = textOf(headerCell);
      var noFilter = headerCell?.dataset?.nofilter === 'true' ||
                     /ação|acoes|actions/i.test(headerLabel);

      if (noFilter) {
        th.innerHTML = '';
      } else {
        var input = document.createElement('input');
        input.type = 'text';
        input.className = 'form-control form-control-sm';
        input.placeholder = headerLabel ? ('Filtrar ' + headerLabel) : 'Filtrar';
        input.setAttribute('data-col-index', String(i));
        input.addEventListener('input', function () {
          applyFilters(table);
        });
        th.appendChild(input);
      }
      filterRow.appendChild(th);
    }
    return filterRow;
  }

  function getFilters(table) {
    var row = table.tHead ? table.tHead.querySelector('.table-filters-row') : null;
    if (!row) return [];
    return Array.from(row.querySelectorAll('input[data-col-index]'));
  }

  function applyFilters(table) {
    var filters = getFilters(table);
    var bodies = Array.from(table.tBodies || []);
    if (!filters.length || !bodies.length) return;

    var activeFilters = filters
      .map(function (inp) { return { idx: parseInt(inp.getAttribute('data-col-index') || '0', 10), val: inp.value.trim().toLowerCase() }; })
      .filter(function (f) { return f.val.length > 0; });

    var globalFilter = (table.getAttribute('data-global-filter') || '').trim().toLowerCase();

    bodies.forEach(function (tbody) {
      Array.from(tbody.rows).forEach(function (tr) {
        var visible = true;
        for (var k = 0; k < activeFilters.length && visible; k++) {
          var f = activeFilters[k];
          var cell = tr.cells[f.idx];
          var cellText = textOf(cell);
          if (cellText.indexOf(f.val) === -1) {
            visible = false;
          }
        }
        if (visible && globalFilter) {
          // must match any cell for global filter
          var anyMatch = false;
          for (var c = 0; c < tr.cells.length; c++) {
            if (textOf(tr.cells[c]).indexOf(globalFilter) !== -1) { anyMatch = true; break; }
          }
          if (!anyMatch) visible = false;
        }
        tr.style.display = visible ? '' : 'none';
      });
    });
  }

  function buildToolbar(table) {
    var toolbar = document.createElement('div');
    toolbar.className = 'table-filter-toolbar d-flex flex-wrap align-items-center gap-2 mb-2';

    var globalInput = document.createElement('input');
    globalInput.type = 'text';
    globalInput.className = 'form-control form-control-sm';
    globalInput.placeholder = 'Pesquisar na tabela';
    globalInput.style.maxWidth = '280px';
    globalInput.addEventListener('input', function () {
      table.setAttribute('data-global-filter', (globalInput.value || '').trim().toLowerCase());
      applyFilters(table);
    });

    var clearBtn = document.createElement('button');
    clearBtn.type = 'button';
    clearBtn.className = 'btn btn-sm btn-outline-secondary';
    clearBtn.textContent = 'Limpar filtros';
    clearBtn.addEventListener('click', function () {
      // clear global
      globalInput.value = '';
      table.removeAttribute('data-global-filter');
      // clear per-column
      getFilters(table).forEach(function (inp) { inp.value = ''; });
      applyFilters(table);
    });

    toolbar.appendChild(globalInput);
    toolbar.appendChild(clearBtn);

    // Insert before the table element, inside the same parent container
    var parent = table.parentNode;
    if (parent) parent.insertBefore(toolbar, table);
  }

  function initTableFilters() {
    var tables = Array.from(document.querySelectorAll('table'));
    tables.forEach(function (table) {
      if (!table || table.dataset.filter === 'off' || table.classList.contains('no-filter')) return;
      if (!table.tHead) return; // require thead to keep structure simple
      if (table.tHead.querySelector('.table-filters-row')) return; // already initialized

      // Add toolbar with global search + clear button
      buildToolbar(table);

      var filterRow = buildFilterRow(table);
      if (filterRow) {
        // Insert after first header row
        var headerRow = table.tHead.rows[0];
        if (headerRow && headerRow.nextSibling) {
          headerRow.parentNode.insertBefore(filterRow, headerRow.nextSibling);
        } else {
          table.tHead.appendChild(filterRow);
        }
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initTableFilters();
    });
  } else {
    initTableFilters();
  }

  // Expose minimal API in case needed elsewhere
  window.TableFilters = {
    init: initTableFilters,
    apply: function () {
      Array.from(document.querySelectorAll('table')).forEach(applyFilters);
    }
  };
})();
