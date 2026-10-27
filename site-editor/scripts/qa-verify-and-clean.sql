SELECT 'Other owner intact' AS check_name, (SELECT count(*) FROM plots WHERE id='other-owner-plot' AND owner_id='qa_other_owner' AND priority='Hold' AND acquisition_date IS NULL) AS plot_count, (SELECT count(*) FROM samples WHERE id='other-owner-sample' AND owner_id='qa_other_owner') AS sample_count;
DELETE FROM samples WHERE owner_id='qa_other_owner';
DELETE FROM plots WHERE owner_id='qa_other_owner';
DELETE FROM mills WHERE owner_id='qa_other_owner';
