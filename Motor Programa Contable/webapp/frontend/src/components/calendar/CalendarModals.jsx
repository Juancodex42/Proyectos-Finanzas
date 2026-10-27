import React from 'react';
import AddCertificationModal from './AddCertificationModal';
import ReplacePeriodModal from './ReplacePeriodModal';
import GuidedResolverModal from './GuidedResolverModal';
import PonteAlDiaModal from './PonteAlDiaModal';
import DeleteConfirmModal from './DeleteConfirmModal';

const CalendarModals = ({
  apiBase,
  showAddModal,
  setShowAddModal,
  addModalPrefill,
  setAddModalPrefill,
  showReplaceModal,
  setShowReplaceModal,
  showResolverModal,
  setShowResolverModal,
  selectedWarning,
  setSelectedWarning,
  showPonteAlDiaModal,
  setShowPonteAlDiaModal,
  deleteConfirm,
  setDeleteConfirm,
  handleDeleteConfirm,
  allWarningsList,
  fetchCertifications,
  fetchWarningsAndGaps,
  showToast,
  selectedYear
}) => {
  return (
    <>
      <AddCertificationModal
        isOpen={showAddModal}
        onClose={() => { setShowAddModal(false); setAddModalPrefill(null); }}
        apiBase={apiBase}
        initialFormData={addModalPrefill}
        onSuccess={() => { fetchCertifications(); fetchWarningsAndGaps(); }}
      />

      <ReplacePeriodModal
        isOpen={showReplaceModal}
        onClose={() => setShowReplaceModal(false)}
        apiBase={apiBase}
        onSuccess={() => { fetchCertifications(); fetchWarningsAndGaps(); }}
        showToast={showToast}
      />

      <GuidedResolverModal
        isOpen={showResolverModal && !!selectedWarning}
        warning={selectedWarning}
        onClose={() => { setShowResolverModal(false); setSelectedWarning(null); }}
        apiBase={apiBase}
        onResolved={() => { fetchWarningsAndGaps(); fetchCertifications(true); }}
        showToast={showToast}
      />

      <PonteAlDiaModal
        isOpen={showPonteAlDiaModal}
        allWarningsList={allWarningsList}
        onClose={() => setShowPonteAlDiaModal(false)}
        apiBase={apiBase}
        onOpenResolver={(item) => { setSelectedWarning(item); setShowResolverModal(true); }}
        onRefresh={() => { fetchWarningsAndGaps(); fetchCertifications(true); }}
        showToast={showToast}
        selectedYear={selectedYear}
      />

      <DeleteConfirmModal
        isOpen={deleteConfirm.show}
        title={deleteConfirm.title}
        onClose={() => setDeleteConfirm({ show: false, id: null, title: '', deleting: false })}
        onConfirm={handleDeleteConfirm}
        deleting={deleteConfirm.deleting}
      />
    </>
  );
};

export default CalendarModals;
